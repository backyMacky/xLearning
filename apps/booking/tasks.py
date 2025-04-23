
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from .utilities import send_session_reminder_email, send_booking_confirmation_email

@shared_task
def send_session_reminders():
    """Celery task to find upcoming sessions and send reminders"""
    from .models import PrivateSessionSlot, GroupSession
    
    # Find sessions starting in approximately 1 hour
    reminder_time = timezone.now() + timedelta(hours=1)
    
    # Allow for 5 minute buffer on either side
    start_window = reminder_time - timedelta(minutes=5)
    end_window = reminder_time + timedelta(minutes=5)
    
    # Query for private sessions
    private_sessions = PrivateSessionSlot.objects.filter(
        start_time__gte=start_window,
        start_time__lte=end_window,
        status='booked'
    ).select_related('student', 'instructor__user')
    
    # Send reminders for private sessions
    for session in private_sessions:
        if session.student:
            send_session_reminder_email(session, session.student)
    
    # Query for group sessions
    group_sessions = GroupSession.objects.filter(
        start_time__gte=start_window,
        start_time__lte=end_window,
        status='scheduled'
    ).prefetch_related('students').select_related('instructor__user')
    
    # Send reminders for group sessions
    for session in group_sessions:
        for student in session.students.all():
            send_session_reminder_email(session, student)
    
    return f"Sent reminders for {private_sessions.count()} private sessions and {group_sessions.count()} group sessions"

@shared_task
def mark_completed_sessions():
    """Celery task to update session statuses after they've ended"""
    from .models import PrivateSessionSlot, GroupSession
    
    now = timezone.now()
    
    # Find private sessions that have ended
    private_sessions = PrivateSessionSlot.objects.filter(
        status='booked',
        end_time__lt=now
    )
    
    # Mark them as completed
    private_completed_count = private_sessions.update(status='completed')
    
    # Find group sessions that have ended
    group_sessions = GroupSession.objects.filter(
        status='scheduled',
        end_time__lt=now
    )
    
    # Mark them as completed
    group_completed_count = group_sessions.update(status='completed')
    
    return f"Marked {private_completed_count} private sessions and {group_completed_count} group sessions as completed"

@shared_task
def clean_duplicate_sessions():
    """Celery task to find and remove duplicate session slots"""
    from .models import PrivateSessionSlot
    from django.db.models import Count
    
    # Find slots with the same instructor and start time
    duplicates = PrivateSessionSlot.objects.values(
        'instructor_id', 'start_time'
    ).annotate(
        count=Count('id')
    ).filter(count__gt=1)
    
    cleaned_count = 0
    
    # For each set of duplicates
    for dup in duplicates:
        # Get all matching slots
        slots = PrivateSessionSlot.objects.filter(
            instructor_id=dup['instructor_id'],
            start_time=dup['start_time']
        ).order_by('id')
        
        # Keep the first one, delete the rest
        if slots.count() > 1:
            # The first slot to keep
            original = slots.first()
            
            # Check if any duplicates are booked
            booked_slots = slots.filter(status='booked')
            
            if booked_slots.exists():
                # If there are booked duplicates, make sure we keep a booked one
                if original.status != 'booked':
                    original = booked_slots.first()
            
            # Get IDs to delete (all except the first/original)
            to_delete_ids = list(slots.exclude(id=original.id).values_list('id', flat=True))
            
            # Delete the duplicates
            delete_count = PrivateSessionSlot.objects.filter(id__in=to_delete_ids).delete()[0]
            cleaned_count += delete_count
    
    return f"Cleaned {cleaned_count} duplicate session slots"