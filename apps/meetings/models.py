from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import uuid


class Meeting(models.Model):
    """Model for virtual meetings and sessions"""
    title = models.CharField(max_length=255)
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='teacher_meetings')
    students = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='student_meetings')
    start_time = models.DateTimeField()
    duration = models.IntegerField(help_text="Duration in minutes")
    meeting_link = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.title} - {self.start_time.strftime('%Y-%m-%d %H:%M')}"
    
    @property
    def end_time(self):
        """Calculate the end time based on start time and duration"""
        return self.start_time + timedelta(minutes=self.duration)
    
    def send_reminders(self):
        """Send email reminders to all participants"""
        # This would be implemented to send emails through Django's email system
        # or integrated with a third-party service
        from django.core.mail import send_mail
        
        subject = f"Reminder: {self.title} starts in 1 hour"
        message = f"""
        Hi there,
        
        This is a reminder that your session "{self.title}" starts in 1 hour at {self.start_time.strftime('%H:%M')}.
        
        Meeting link: {self.meeting_link}
        Duration: {self.duration} minutes
        
        Best regards,
        Learning Platform Team
        """
        
        # Get all participants' emails
        teacher_email = self.teacher.email
        student_emails = [student.email for student in self.students.all()]
        all_emails = [teacher_email] + student_emails
        
        # Send the reminder email
        send_mail(
            subject=subject,
            message=message,
            from_email="noreply@learningplatform.com",
            recipient_list=all_emails,
            fail_silently=False,
        )
    
    class Meta:
        app_label = 'meetings'


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