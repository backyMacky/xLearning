
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils import timezone
from datetime import timedelta, datetime
import urllib.parse


def generate_google_calendar_link(session):
    """Generate a Google Calendar event link for a session
    
    Args:
        session: Either a PrivateSessionSlot or GroupSession instance
    
    Returns:
        str: URL for creating a Google Calendar event
    """
    # Format session details
    if hasattr(session, 'instructor') and hasattr(session.instructor, 'user'):
        instructor_name = session.instructor.user.username
    else:
        instructor_name = "Your Instructor"
    
    if hasattr(session, 'title'):
        # Group session
        title = f"Group Language Session: {session.title}"
        details = f"Group language learning session on {session.language} ({session.level}).\n\n"
        if hasattr(session, 'description') and session.description:
            details += session.description
    else:
        # Private session
        title = f"Private Language Session with {instructor_name}"
        details = f"One-on-one language learning session with {instructor_name}.\n\n"
        if hasattr(session, 'language') and session.language:
            lang_display = dict(session.LANGUAGE_CHOICES).get(session.language, session.language)
            level_display = dict(session.LEVEL_CHOICES).get(session.level, session.level)
            details += f"Language: {lang_display} - Level: {level_display}"
    
    # Add meeting link to details if available
    if hasattr(session, 'meeting') and session.meeting and session.meeting.meeting_link:
        details += f"\n\nJoin URL: {session.meeting.meeting_link}"
    
    # Format dates for Google Calendar
    start_time = session.start_time.strftime('%Y%m%dT%H%M%S')
    end_time = session.end_time.strftime('%Y%m%dT%H%M%S')
    
    # Format location
    location = "Online Meeting"
    if hasattr(session, 'meeting') and session.meeting and session.meeting.meeting_link:
        location = session.meeting.meeting_link
    
    # Encode parameters for URL
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

def generate_ical_file_content(session):
    """Generate iCalendar (.ics) file content for a session
    
    Args:
        session: Either a PrivateSessionSlot or GroupSession instance
    
    Returns:
        str: Content for an .ics file
    """
    import uuid
    from datetime import datetime
    
    # Format session details
    if hasattr(session, 'instructor') and hasattr(session.instructor, 'user'):
        instructor_name = session.instructor.user.username
    else:
        instructor_name = "Your Instructor"
    
    if hasattr(session, 'title'):
        # Group session
        summary = f"Group Language Session: {session.title}"
        description = f"Group language learning session on {session.language} ({session.level}).\n\n"
        if hasattr(session, 'description') and session.description:
            description += session.description
    else:
        # Private session
        summary = f"Private Language Session with {instructor_name}"
        description = f"One-on-one language learning session with {instructor_name}.\n\n"
        if hasattr(session, 'language') and session.language:
            lang_display = dict(session.LANGUAGE_CHOICES).get(session.language, session.language)
            level_display = dict(session.LEVEL_CHOICES).get(session.level, session.level)
            description += f"Language: {lang_display} - Level: {level_display}"
    
    # Add meeting link to description if available
    if hasattr(session, 'meeting') and session.meeting and session.meeting.meeting_link:
        description += f"\n\nJoin URL: {session.meeting.meeting_link}"
    
    # Format location
    location = "Online Meeting"
    if hasattr(session, 'meeting') and session.meeting and session.meeting.meeting_link:
        location = session.meeting.meeting_link
    
    # Format dates for iCalendar
    start_time = session.start_time.strftime('%Y%m%dT%H%M%SZ')
    end_time = session.end_time.strftime('%Y%m%dT%H%M%SZ')
    
    # Generate a unique ID for the event
    uid = str(uuid.uuid4())
    
    # Create the iCalendar content
    ical_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Learning Platform//Session Calendar//EN
CALSCALE:GREGORIAN
BEGIN:VEVENT
SUMMARY:{summary}
DTSTART:{start_time}
DTEND:{end_time}
DESCRIPTION:{description}
LOCATION:{location}
STATUS:CONFIRMED
SEQUENCE:0
UID:{uid}
END:VEVENT
END:VCALENDAR"""
    
    return ical_content


# Booking confirmation and cancellation emails
def send_booking_confirmation_email(session, user):
    """Send a booking confirmation email to the user
    
    Args:
        session: PrivateSessionSlot or GroupSession instance
        user: User who booked the session
    """
    # Get instructor name
    if hasattr(session, 'instructor') and hasattr(session.instructor, 'user'):
        instructor_name = session.instructor.user.username
    else:
        instructor_name = "Your Instructor"
        
    # Format session times
    session_date = session.start_time.strftime('%A, %B %d, %Y')
    session_time = session.start_time.strftime('%I:%M %p')
    
    # Get meeting link if available
    meeting_link = None
    if hasattr(session, 'meeting') and session.meeting:
        meeting_link = session.meeting.meeting_link
    
    # Generate Google Calendar link
    from .utilities import generate_google_calendar_link
    google_calendar_link = generate_google_calendar_link(session)
    
    # Prepare context for the email template
    context = {
        'user': user,
        'instructor': instructor_name,
        'session_date': session_date,
        'session_time': session_time,
        'session_duration': session.duration_minutes,
        'meeting_link': meeting_link,
        'google_calendar_link': google_calendar_link
    }
    
    # Render and send email
    html_message = render_to_string('email/booking_confirmation.html', context)
    plain_message = strip_tags(html_message)
    
    send_mail(
        subject=f"Your session with {instructor_name} is confirmed!",
        message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=html_message,
        fail_silently=True
    )

def send_cancellation_email(session, user, refund_amount=0):
    """Send a cancellation notification email to the user
    
    Args:
        session: PrivateSessionSlot or GroupSession instance
        user: User whose session was cancelled
        refund_amount: Amount of credits refunded (default 0)
    """
    # Get instructor name
    if hasattr(session, 'instructor') and hasattr(session.instructor, 'user'):
        instructor_name = session.instructor.user.username
    else:
        instructor_name = "Your Instructor"
        
    # Format session times
    session_date = session.start_time.strftime('%A, %B %d, %Y')
    session_time = session.start_time.strftime('%I:%M %p')
    
    # Prepare context for the email template
    context = {
        'user': user,
        'instructor': instructor_name,
        'session_date': session_date,
        'session_time': session_time,
        'refund_amount': refund_amount
    }
    
    # Render and send email
    html_message = render_to_string('email/session_cancelled_by_instructor.html', context)
    plain_message = strip_tags(html_message)
    
    send_mail(
        subject=f"Your session with {instructor_name} has been cancelled",
        message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=html_message,
        fail_silently=True
    )

def send_session_reminder_email(session, user):
    """Send a reminder email to the user before their session
    
    Args:
        session: PrivateSessionSlot or GroupSession instance
        user: User who has the upcoming session
    """
    # Get instructor name
    if hasattr(session, 'instructor') and hasattr(session.instructor, 'user'):
        instructor_name = session.instructor.user.username
    else:
        instructor_name = "Your Instructor"
        
    # Format session times
    session_date = session.start_time.strftime('%A, %B %d, %Y')
    session_time = session.start_time.strftime('%I:%M %p')
    
    # Get meeting link if available
    meeting_link = None
    if hasattr(session, 'meeting') and session.meeting:
        meeting_link = session.meeting.meeting_link
    
    # Prepare context for the email template
    context = {
        'user': user,
        'instructor': instructor_name,
        'session_date': session_date,
        'session_time': session_time,
        'session_duration': session.duration_minutes,
        'meeting_link': meeting_link
    }
    
    # Render and send email
    html_message = render_to_string('email/session_reminder.html', context)
    plain_message = strip_tags(html_message)
    
    send_mail(
        subject=f"Reminder: Your session with {instructor_name} starts in 1 hour",
        message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=html_message,
        fail_silently=True
    )

def schedule_session_reminders():
    """
    Function to find upcoming sessions and send reminders
    This function should be called by a scheduler like Celery
    """
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