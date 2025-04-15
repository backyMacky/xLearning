from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.models import User
from .models import Course, Lesson, Resource

@login_required
def course_list(request):
    """List all courses"""
    if request.user.is_teacher:
        # Teachers see their own courses
        courses = Course.objects.filter(teacher=request.user)
    else:
        # Students see enrolled courses
        courses = request.user.enrolled_courses.all()
    
    # If we want to show recommended or available courses to students
    available_courses = []
    if request.user.is_student:
        # Get courses the student is not enrolled in
        available_courses = Course.objects.exclude(id__in=request.user.enrolled_courses.values_list('id', flat=True))
    
    return render(request, 'content/course_list.html', {
        'courses': courses,
        'available_courses': available_courses
    })

@login_required
def course_detail(request, course_id):
    """View a specific course"""
    course = get_object_or_404(Course, id=course_id)
    
    # Check if user has access
    if request.user.is_teacher and course.teacher != request.user:
        return redirect('content:course_list')
    
    if request.user.is_student and course not in request.user.enrolled_courses.all():
        # Show preview for enrollment
        return render(request, 'content/course_preview.html', {'course': course})
    
    lessons = course.lessons.all().order_by('order')
    
    return render(request, 'content/course_detail.html', {
        'course': course,
        'lessons': lessons
    })

@login_required
def create_course(request):
    """Create a new course (for teachers)"""
    if not request.user.is_teacher:
        return redirect('content:course_list')
    
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        
        course = Course.objects.create(
            title=title,
            description=description,
            teacher=request.user
        )
        
        return redirect('content:course_detail', course_id=course.id)
    
    # GET request
    return render(request, 'content/create_course.html')

@login_required
def edit_course(request, course_id):
    """Edit an existing course"""
    course = get_object_or_404(Course, id=course_id, teacher=request.user)
    
    if request.method == 'POST':
        course.title = request.POST.get('title', course.title)
        course.description = request.POST.get('description', course.description)
        course.save()
        
        return redirect('content:course_detail', course_id=course.id)
    
    # GET request
    return render(request, 'content/edit_course.html', {'course': course})

@login_required
def enroll_course(request, course_id):
    """Enroll in a course (for students)"""
    if not request.user.is_student:
        return redirect('content:course_list')
    
    course = get_object_or_404(Course, id=course_id)
    
    # Check if already enrolled
    if course in request.user.enrolled_courses.all():
        return redirect('content:course_detail', course_id=course.id)
    
    # Enroll the student
    course.add_student(request.user)
    
    return redirect('content:course_detail', course_id=course.id)

@login_required
def unenroll_course(request, course_id):
    """Unenroll from a course"""
    if not request.user.is_student:
        return redirect('content:course_list')
    
    course = get_object_or_404(Course, id=course_id)
    
    # Check if enrolled
    if course not in request.user.enrolled_courses.all():
        return redirect('content:course_list')
    
    # Unenroll
    course.remove_student(request.user)
    
    return redirect('content:course_list')

@login_required
def lesson_detail(request, lesson_id):
    """View a specific lesson"""
    lesson = get_object_or_404(Lesson, id=lesson_id)
    course = lesson.course
    
    # Check if user has access
    if request.user.is_teacher and course.teacher != request.user:
        return redirect('content:course_list')
    
    if request.user.is_student and course not in request.user.enrolled_courses.all():
        return redirect('content:course_list')
    
    # Get next lesson for navigation
    next_lesson = lesson.get_next_lesson()
    
    return render(request, 'content/lesson_detail.html', {
        'lesson': lesson,
        'course': course,
        'next_lesson': next_lesson
    })

@login_required
def create_lesson(request, course_id):
    """Create a new lesson (for teachers)"""
    course = get_object_or_404(Course, id=course_id, teacher=request.user)
    
    if request.method == 'POST':
        title = request.POST.get('title')
        content = request.POST.get('content')
        video_url = request.POST.get('video_url')
        
        # Calculate order (append to end)
        order = course.lessons.count()
        
        lesson = Lesson.objects.create(
            course=course,
            title=title,
            content=content,
            video_url=video_url,
            order=order
        )
        
        # Handle attachment if provided
        if 'attachment' in request.FILES:
            lesson.attachment = request.FILES['attachment']
            lesson.save()
        
        return redirect('content:lesson_detail', lesson_id=lesson.id)
    
    # GET request
    return render(request, 'content/create_lesson.html', {'course': course})

@login_required
def edit_lesson(request, lesson_id):
    """Edit an existing lesson"""
    lesson = get_object_or_404(Lesson, id=lesson_id)
    
    # Check permissions
    if not request.user.is_teacher or lesson.course.teacher != request.user:
        return redirect('content:course_list')
    
    if request.method == 'POST':
        lesson.title = request.POST.get('title', lesson.title)
        lesson.content = request.POST.get('content', lesson.content)
        lesson.video_url = request.POST.get('video_url', lesson.video_url)
        
        # Handle attachment update
        if 'attachment' in request.FILES:
            lesson.attachment = request.FILES['attachment']
        
        lesson.save()
        
        return redirect('content:lesson_detail', lesson_id=lesson.id)
    
    # GET request
    return render(request, 'content/edit_lesson.html', {'lesson': lesson})

@login_required
def resource_list(request):
    """List all resources"""
    if request.user.is_teacher:
        # Show resources created by this teacher
        resources = Resource.objects.filter(created_by=request.user)
    else:
        # Show resources assigned to this student
        resources = request.user.assigned_resources.all()
    
    return render(request, 'content/resource_list.html', {'resources': resources})

@login_required
def create_resource(request):
    """Create a new resource (for teachers)"""
    if not request.user.is_teacher:
        return redirect('content:resource_list')
    
    if request.method == 'POST':
        title = request.POST.get('title')
        resource_type = request.POST.get('type')
        
        # Create the resource
        resource = Resource.objects.create(
            title=title,
            type=resource_type,
            created_by=request.user
        )
        
        # Handle file upload
        if 'file' in request.FILES:
            resource.file = request.FILES['file']
            resource.save()
        
        # Handle sharing with users or courses
        if 'share_with_users' in request.POST:
            user_ids = request.POST.getlist('share_with_users')
            users = User.objects.filter(id__in=user_ids)
            resource.share(users)
        
        return redirect('content:resource_list')
    
    # GET request
    return render(request, 'content/create_resource.html')