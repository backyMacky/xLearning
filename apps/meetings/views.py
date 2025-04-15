from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib.auth.models import User
from .models import Meeting, TeacherAvailability
from django.utils import timezone
from datetime import datetime, timedelta

@login_required
def meeting_list(request):
    """List all meetings for the user"""
    now = timezone.now()
    
    if request.user.is_teacher:
        # Get teacher's meetings
        upcoming_meetings = Meeting.objects.filter(
            teacher=request.user,
            start_time__gte=now
        ).order_by('start_time')
        
        past_meetings = Meeting.objects.filter(
            teacher=request.user,
            start_time__lt=now
        ).order_by('-start_time')
    else:
        # Get student's meetings
        upcoming_meetings = Meeting.objects.filter(
            students=request.user,
            start_time__gte=now
        ).order_by('start_time')
        
        past_meetings = Meeting.objects.filter(
            students=request.user,
            start_time__lt=now
        ).order_by('-start_time')
    
    return render(request, 'meetings/meeting_list.html', {
        'upcoming_meetings': upcoming_meetings,
        'past_meetings': past_meetings
    })

@login_required
def meeting_detail(request, meeting_id):
    """View a specific meeting"""
    meeting = get_object_or_404(Meeting, id=meeting_id)
    
    # Check if user has access to this meeting
    if request.user.is_teacher and meeting.teacher != request.user:
        return redirect('meetings:meeting_list')
    
    if request.user.is_student and request.user not in meeting.students.all():
        return redirect('meetings:meeting_list')
    
    return render(request, 'meetings/meeting_detail.html', {'meeting': meeting})

@login_required
def create_meeting(request):
    """Create a new meeting (for teachers)"""
    if not request.user.is_teacher:
        return redirect('meetings:meeting_list')
    
    if request.method == 'POST':
        title = request.POST.get('title')
        start_time_str = request.POST.get('start_time')
        duration = int(request.POST.get('duration', 60))
        student_ids = request.POST.getlist('students')
        
        # Parse start time
        start_time = datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M')
        
        # Create meeting with a default meeting link (in a real app, this would integrate with Zoom/Meet/etc.)
        meeting = Meeting.objects.create(
            title=title,
            teacher=request.user,
            start_time=start_time,
            duration=duration,
            meeting_link=f"https://meet.google.com/{request.user.username}-{timezone.now().strftime('%Y%m%d%H%M')}"
        )
        
        # Add students
        for student_id in student_ids:
            try:
                student = User.objects.get(id=student_id)
                meeting.students.add(student)
            except User.DoesNotExist:
                pass
        
        return redirect('meetings:meeting_detail', meeting_id=meeting.id)
    
    # GET request
    # Get students the teacher has access to (e.g., from their courses)
    students = User.objects.filter(is_student=True, enrolled_courses__teacher=request.user).distinct()
    
    return render(request, 'meetings/create_meeting.html', {'students': students})

@login_required
def edit_meeting(request, meeting_id):
    """Edit an existing meeting"""
    meeting = get_object_or_404(Meeting, id=meeting_id, teacher=request.user)
    
    # Prevent editing past meetings
    if meeting.start_time < timezone.now():
        return redirect('meetings:meeting_detail', meeting_id=meeting.id)
    
    if request.method == 'POST':
        meeting.title = request.POST.get('title', meeting.title)
        
        start_time_str = request.POST.get('start_time')
        if start_time_str:
            meeting.start_time = datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M')
            
        duration = request.POST.get('duration')
        if duration:
            meeting.duration = int(duration)
            
        # Update meeting link if needed
        new_link = request.POST.get('meeting_link')
        if new_link:
            meeting.meeting_link = new_link
            
        meeting.save()
        
        # Update students
        if 'students' in request.POST:
            student_ids = request.POST.getlist('students')
            # Clear existing students
            meeting.students.clear()
            
            # Add new students
            for student_id in student_ids:
                try:
                    student = User.objects.get(id=student_id)
                    meeting.students.add(student)
                except User.DoesNotExist:
                    pass
        
        return redirect('meetings:meeting_detail', meeting_id=meeting.id)
    
    # GET request
    students = User.objects.filter(is_student=True, enrolled_courses__teacher=request.user).distinct()
    
    return render(request, 'meetings/edit_meeting.html', {
        'meeting': meeting,
        'students': students
    })

@login_required
def cancel_meeting(request, meeting_id):
    """Cancel a meeting"""
    meeting = get_object_or_404(Meeting, id=meeting_id, teacher=request.user)
    
    # Prevent cancelling past meetings
    if meeting.start_time < timezone.now():
        return redirect('meetings:meeting_detail', meeting_id=meeting.id)
    
    if request.method == 'POST':
        # In a real app, you might want to:
        # 1. Send cancellation emails to participants
        # 2. Create a cancellation record instead of deleting
        
        # For now, just delete the meeting
        meeting.delete()
        
        return redirect('meetings:meeting_list')
    
    # GET request (confirmation page)
    return render(request, 'meetings/confirm_cancel.html', {'meeting': meeting})

@login_required
def send_meeting_reminder(request, meeting_id):
    """Manually send reminders for a meeting"""
    meeting = get_object_or_404(Meeting, id=meeting_id, teacher=request.user)
    
    # Send reminders
    meeting.send_reminders()
    
    return redirect('meetings:meeting_detail', meeting_id=meeting.id)

@login_required
def availability_list(request):
    """List teacher availability settings"""
    if not request.user.is_teacher:
        return redirect('meetings:meeting_list')
    
    availability_slots = TeacherAvailability.objects.filter(teacher=request.user).order_by('day_of_week', 'start_time')
    
    return render(request, 'meetings/availability_list.html', {'availability_slots': availability_slots})

@login_required
def create_availability(request):
    """Create a new availability slot (for teachers)"""
    if not request.user.is_teacher:
        return redirect('meetings:meeting_list')
    
    if request.method == 'POST':
        day_of_week = int(request.POST.get('day_of_week'))
        start_time_str = request.POST.get('start_time')
        end_time_str = request.POST.get('end_time')
        
        # Parse times
        start_time = datetime.strptime(start_time_str, '%H:%M').time()
        end_time = datetime.strptime(end_time_str, '%H:%M').time()
        
        # Create availability slot
        TeacherAvailability.objects.create(
            teacher=request.user,
            day_of_week=day_of_week,
            start_time=start_time,
            end_time=end_time
        )
        
        return redirect('meetings:availability_list')
    
    # GET request
    return render(request, 'meetings/create_availability.html')

@login_required
def delete_availability(request, availability_id):
    """Delete an availability slot"""
    availability = get_object_or_404(TeacherAvailability, id=availability_id, teacher=request.user)
    
    if request.method == 'POST':
        availability.delete()
        return redirect('meetings:availability_list')
    
    # GET request (confirmation page)
    return render(request, 'meetings/confirm_delete_availability.html', {'availability': availability})