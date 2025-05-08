from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from .models import Meeting, TeacherAvailability

    
import logging

logger = logging.getLogger(__name__)

@shared_task
def send_meeting_reminders():
    """Celery task to send meeting reminders for upcoming meetings"""
    
    
    # Find meetings starting in approximately 1 hour
    reminder_time = timezone.now() + timedelta(hours=1)
    
    # Allow for 5 minute buffer on either side
    start_window = reminder_time - timedelta(minutes=5)
    end_window = reminder_time + timedelta(minutes=5)
    
    # Find meetings that start within the window and haven't been cancelled
    upcoming_meetings = Meeting.objects.filter(
        start_time__gte=start_window,
        start_time__lte=end_window,
        status='scheduled'
    ).select_related('teacher').prefetch_related('students')
    
    reminder_count = 0
    meeting_count = upcoming_meetings.count()
    
    # Send reminders for each meeting
    for meeting in upcoming_meetings:
        try:
            sent = meeting.send_reminders()
            reminder_count += sent
            logger.info(f"Sent {sent} reminders for meeting {meeting.id}: {meeting.title}")
        except Exception as e:
            logger.error(f"Failed to send reminders for meeting {meeting.id}: {str(e)}")
    
    logger.info(f"Meeting reminder task complete. Sent {reminder_count} reminders for {meeting_count} meetings")
    return f"Sent {reminder_count} reminders for {meeting_count} meetings"


@shared_task
def update_meeting_statuses():
    """Update status of meetings based on their time"""
    
    now = timezone.now()
    
    # Mark meetings as in_progress if they've started but not ended
    in_progress_count = Meeting.objects.filter(
        start_time__lte=now,
        start_time__gt=now - timedelta(minutes=24*60),  # Limit to last 24 hours
        status='scheduled'
    ).update(status='in_progress')
    
    # Mark meetings as completed if they've ended
    completed_meetings = Meeting.objects.filter(
        status__in=['scheduled', 'in_progress'],
    ).select_related('teacher')
    
    completed_count = 0
    for meeting in completed_meetings:
        if now > meeting.end_time:
            meeting.status = 'completed'
            meeting.save(update_fields=['status'])
            completed_count += 1
    
    logger.info(f"Updated meeting statuses: {in_progress_count} in progress, {completed_count} completed")
    return f"Updated meeting statuses: {in_progress_count} in progress, {completed_count} completed"


@shared_task
def generate_availability_slots():
    """Generate booking slots from teacher availability preferences"""
    
    availabilities = TeacherAvailability.objects.filter(is_recurring=True)
    
    total_slots_created = 0
    
    for availability in availabilities:
        try:
            slots_created = availability.create_booking_slots(weeks_ahead=4)
            total_slots_created += slots_created
            logger.info(f"Created {slots_created} booking slots for {availability.teacher.username}")
        except Exception as e:
            logger.error(f"Failed to create booking slots for {availability}: {str(e)}")
    
    logger.info(f"Availability slot generation complete. Created {total_slots_created} slots")
    return f"Created {total_slots_created} booking slots from availability templates"


@shared_task
def clean_old_meetings():
    """Archive or clean up old meetings that are no longer needed in active view"""
    
    # Find meetings older than 90 days that are completed
    cutoff_date = timezone.now() - timedelta(days=90)
    old_meetings = Meeting.objects.filter(
        end_time__lt=cutoff_date,
        status='completed'
    )
    
    # In a real app, you might archive these meetings to another table
    # or perform other cleanup operations
    
    # For this demo, we'll just count them
    old_meeting_count = old_meetings.count()
    
    logger.info(f"Found {old_meeting_count} old meetings that could be archived")
    return f"Found {old_meeting_count} old meetings that could be archived"