from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from .models import Course, Lesson

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