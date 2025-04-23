from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404

from apps.booking.models import GroupSession
from .models import Course, Lesson, PrivateSession

@login_required
def get_course_lessons(request, course_id):
    """API endpoint to get lessons for a specific course"""
    course = get_object_or_404(Course, id=course_id)
    
    # Check permissions
    if not request.user.is_superuser:
        if request.user.is_teacher and course.teacher != request.user:
            return JsonResponse({'error': 'Permission denied'}, status=403)
        elif request.user.is_student and course not in request.user.enrolled_courses.all():
            return JsonResponse({'error': 'Permission denied'}, status=403)
    
    # Get all lessons from all modules in the course
    lessons = []
    for module in course.modules.all().order_by('order'):
        for lesson in module.lessons.all().order_by('order'):
            lessons.append({
                'id': lesson.id,
                'title': f"{module.title} - {lesson.title}",
                'module_id': module.id,
                'module_title': module.title,
            })
    
    return JsonResponse(lessons, safe=False)

@login_required
def mark_lesson_complete(request, lesson_id):
    """Mark a lesson as complete/incomplete for a student"""
    if not request.user.is_student:
        return JsonResponse({'error': 'Only students can mark lessons'}, status=403)
    
    lesson = get_object_or_404(Lesson, id=lesson_id)
    course = lesson.module.course
    
    # Check if student is enrolled in the course
    if course not in request.user.enrolled_courses.all():
        return JsonResponse({'error': 'You are not enrolled in this course'}, status=403)
    
    # Get or create course progress
    from .models import CourseProgress, LessonCompletion
    progress, created = CourseProgress.objects.get_or_create(
        student=request.user,
        course=course
    )
    
    action = request.POST.get('action', 'complete')
    
    if action == 'complete':
        # Mark lesson as complete
        LessonCompletion.objects.get_or_create(
            student=request.user,
            lesson=lesson
        )
        return JsonResponse({'status': 'success', 'completed': True})
    else:
        # Mark lesson as incomplete
        LessonCompletion.objects.filter(
            student=request.user,
            lesson=lesson
        ).delete()
        return JsonResponse({'status': 'success', 'completed': False})
    

@login_required
def get_meeting_link(request, session_type, session_id):
    """API endpoint to get or generate meeting link for a session"""
    try:
        if session_type == 'private':
            session = get_object_or_404(PrivateSession, id=session_id)
            
            # Check permissions
            if not request.user.is_superuser:
                if request.user != session.instructor.user and request.user != session.student:
                    return JsonResponse({'error': 'Permission denied'}, status=403)
                    
            # Get or create meeting
            if session.meeting:
                meeting_link = session.meeting.meeting_link
            else:
                # Create a meeting
                import uuid
                meeting_code = str(uuid.uuid4()).replace('-', '')[:10]
                meeting_link = f"https://meet.google.com/{meeting_code}"
                
                # Create a Meeting instance
                from apps.meetings.models import Meeting
                meeting = Meeting.objects.create(
                    title=f"Private Session: {session.instructor.user.username} and {session.student.username}",
                    teacher=session.instructor.user,
                    start_time=session.start_time,
                    duration=session.duration_minutes,
                    meeting_link=meeting_link
                )
                meeting.students.add(session.student)
                
                # Link meeting to session
                session.meeting = meeting
                session.save()
            
            return JsonResponse({'meeting_link': meeting_link, 'status': 'success'})
            
        elif session_type == 'group':
            session = get_object_or_404(GroupSession, id=session_id)
            
            # Check permissions
            if not request.user.is_superuser:
                if request.user != session.instructor.user and request.user not in session.students.all():
                    return JsonResponse({'error': 'Permission denied'}, status=403)
                    
            # Get or create meeting
            if session.meeting:
                meeting_link = session.meeting.meeting_link
            else:
                # Create a meeting
                import uuid
                meeting_code = str(uuid.uuid4()).replace('-', '')[:10]
                meeting_link = f"https://meet.google.com/{meeting_code}"
                
                # Create a Meeting instance
                from apps.meetings.models import Meeting
                meeting = Meeting.objects.create(
                    title=f"Group Session: {session.title}",
                    teacher=session.instructor.user,
                    start_time=session.start_time,
                    duration=session.duration_minutes,
                    meeting_link=meeting_link
                )
                
                # Add all students to the meeting
                for student in session.students.all():
                    meeting.students.add(student)
                
                # Link meeting to session
                session.meeting = meeting
                session.save()
            
            return JsonResponse({'meeting_link': meeting_link, 'status': 'success'})
            
        else:
            return JsonResponse({'error': 'Invalid session type'}, status=400)
            
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)    