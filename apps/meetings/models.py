from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
import urllib.parse        
import uuid
import logging

logger = logging.getLogger(__name__)

class Meeting(models.Model):
    """Model for virtual meetings and sessions"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='teacher_meetings')
    students = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='student_meetings')
    start_time = models.DateTimeField()
    duration = models.IntegerField(help_text="Duration in minutes")
    meeting_link = models.CharField(max_length=255, blank=True, null=True)
    meeting_code = models.CharField(max_length=30, blank=True, null=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=20, choices=[
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], default='scheduled')
    notes = models.TextField(blank=True, null=True, help_text="Meeting notes or agenda")
    recording_url = models.URLField(blank=True, null=True, help_text="URL to recorded session if available")
    
    def __str__(self):
        return f"{self.title} - {self.start_time.strftime('%Y-%m-%d %H:%M')}"
    
    def save(self, *args, **kwargs):
        """Override save to generate meeting code and link if not provided"""
        if not self.meeting_code:
            # Generate a short unique code from the UUID
            self.meeting_code = str(self.id).replace('-', '')[:12]
            
        if not self.meeting_link:
            # Generate a Google Meet link with the unique code
            self.generate_meeting_link()
            
        super().save(*args, **kwargs)
    
    @property
    def end_time(self):
        """Calculate the end time based on start time and duration"""
        return self.start_time + timedelta(minutes=self.duration)
    
    @property
    def is_active(self):
        """Check if meeting is currently active"""
        now = timezone.now()
        return self.start_time <= now <= self.end_time and self.status != 'cancelled'
    
    @property
    def is_upcoming(self):
        """Check if meeting is upcoming"""
        now = timezone.now()
        return self.start_time > now and self.status != 'cancelled'
    
    @property
    def google_calendar_link(self):
        """Generate a Google Calendar link for this meeting"""
        start_time = self.start_time.strftime('%Y%m%dT%H%M%S')
        end_time = self.end_time.strftime('%Y%m%dT%H%M%S')
        title = f"Meeting: {self.title}"
        details = f"Meeting with {self.teacher.username}"
        if self.meeting_link:
            details += f"\nJoin URL: {self.meeting_link}"
        location = self.meeting_link if self.meeting_link else "Online Meeting"
        
        # Format parameters for URL
        
        params = {
            'action': 'TEMPLATE',
            'text': urllib.parse.quote(title),
            'dates': f"{start_time}/{end_time}",
            'details': urllib.parse.quote(details),
            'location': urllib.parse.quote(location)
        }
        
        # Build the Google Calendar URL
        base_url = "https://calendar.google.com/calendar/render"
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        calendar_url = f"{base_url}?{query_string}"
        
        return calendar_url
    
    def generate_meeting_link(self):
        """Generate an improved Google Meet link for this meeting using UUID"""
        # Format the meeting code from the UUID if not already set
        if not self.meeting_code:
            self.meeting_code = str(uuid.uuid4()).replace('-', '')[:12]
        
        # Create a properly formatted Google Meet link
        # The 'lookup' format is more robust in development environments
        self.meeting_link = f"https://meet.google.com/lookup/{self.meeting_code}?authuser=0&hs=179"
        
        # Alternative formats that might work better in production:
        # Standard meet format: https://meet.google.com/abc-defg-hij
        # hyphenated_code = f"{self.meeting_code[:3]}-{self.meeting_code[3:7]}-{self.meeting_code[7:10]}"
        # self.meeting_link = f"https://meet.google.com/{hyphenated_code}"
        
        return self.meeting_link
    
    def send_reminders(self):
        """Send email reminders to all participants"""
        
        subject = f"Reminder: {self.title} starts in 1 hour"
        
        # Get all participants' emails
        teacher_email = self.teacher.email
        student_emails = [student.email for student in self.students.all()]
        all_emails = [teacher_email] + student_emails
        
        sent_count = 0
        
        # Send to each participant with personalized template
        for email in all_emails:
            try:
                # Determine if this is teacher or student
                is_teacher = email == teacher_email
                user = self.teacher if is_teacher else self.students.get(email=email)
                
                # Prepare context for the email template
                context = {
                    'user': user,
                    'instructor': self.teacher.username,
                    'session_date': self.start_time.strftime('%A, %B %d, %Y'),
                    'session_time': self.start_time.strftime('%I:%M %p'),
                    'session_duration': self.duration,
                    'meeting_link': self.meeting_link,
                    'meeting_id': self.meeting_code,
                    'site_name': 'Learning Platform',
                    'site_url': '/',
                }
                
                # Render the email template
                html_message = render_to_string('email/session_reminder.html', context)
                plain_message = strip_tags(html_message)
                
                # Send the email
                send_mail(
                    subject=subject,
                    message=plain_message,
                    from_email="noreply@learningplatform.com",
                    recipient_list=[email],
                    html_message=html_message,
                    fail_silently=False,
                )
                
                sent_count += 1
                logger.info(f"Sent reminder email to {email} for meeting {self.id}")
            except Exception as e:
                logger.error(f"Failed to send reminder to {email}: {str(e)}")
        
        return sent_count
    
    def mark_as_completed(self):
        """Mark meeting as completed if it's in the past"""
        if timezone.now() > self.end_time and self.status == 'scheduled':
            self.status = 'completed'
            self.save(update_fields=['status'])
            return True
        return False
    
    def cancel(self, notify_participants=True):
        """Cancel the meeting and optionally notify participants"""
        if self.status == 'completed':
            return False, "Cannot cancel a completed meeting"
        
        self.status = 'cancelled'
        self.save(update_fields=['status'])
        
        if notify_participants:
            self.send_cancellation_notices()
        
        return True, "Meeting cancelled successfully"
    
    def send_cancellation_notices(self):
        """Send cancellation notices to all participants"""
        
        subject = f"Cancellation Notice: {self.title}"
        
        # Get all participants' emails
        teacher_email = self.teacher.email
        student_emails = [student.email for student in self.students.all()]
        all_emails = [teacher_email] + student_emails
        
        # Exclude the cancelling user (assumed to be the teacher)
        recipient_emails = student_emails
        
        # Prepare context for the email template
        for email in recipient_emails:
            try:
                user = self.students.get(email=email)
                
                context = {
                    'user': user,
                    'instructor': self.teacher.username,
                    'session_date': self.start_time.strftime('%A, %B %d, %Y'),
                    'session_time': self.start_time.strftime('%I:%M %p'),
                    'session_title': self.title,
                    'meeting_id': self.meeting_code,
                    'site_name': 'Learning Platform',
                    'site_url': '/',
                }
                
                # Render the email template
                html_message = render_to_string('email/session_cancelled_by_instructor.html', context)
                plain_message = strip_tags(html_message)
                
                # Send the email
                send_mail(
                    subject=subject,
                    message=plain_message,
                    from_email="noreply@learningplatform.com",
                    recipient_list=[email],
                    html_message=html_message,
                    fail_silently=True,
                )
                logger.info(f"Sent cancellation notice to {email} for meeting {self.id}")
            except Exception as e:
                logger.error(f"Failed to send cancellation notice to {email}: {str(e)}")
    
    class Meta:
        app_label = 'meetings'
        ordering = ['-start_time']
        indexes = [
            models.Index(fields=['start_time']),
            models.Index(fields=['status']),
            models.Index(fields=['teacher']),
        ]




class TeacherAvailability(models.Model):
    """Model for teacher availability slots"""
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='availability_slots')
    day_of_week = models.IntegerField(choices=[
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday'),
    ])
    start_time = models.TimeField()
    end_time = models.TimeField()
    
    def __str__(self):
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        return f"{self.teacher.username} - {days[self.day_of_week]}: {self.start_time} - {self.end_time}"
    
    def is_available(self):
        """Check if this availability slot is currently active"""
        # Check if the slot is for today and current time is within range
        now = timezone.now()
        current_day_of_week = now.weekday()
        current_time = now.time()
        
        if self.day_of_week == current_day_of_week and self.start_time <= current_time <= self.end_time:
            return True
        return False
    
    class Meta:
        app_label = 'meetings'        