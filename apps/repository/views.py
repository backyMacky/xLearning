from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from .models import StudentFile, TeacherResource, ResourceAccess, ResourceCollection
import mimetypes
import os

@login_required
def file_dashboard(request):
    """Dashboard showing user's files and resources"""
    if request.user.is_teacher:
        # Teachers see their own uploaded resources
        resources = TeacherResource.objects.filter(teacher=request.user).order_by('-upload_date')
        collections = ResourceCollection.objects.filter(owner=request.user).order_by('name')
        
        return render(request, 'repository/teacher_dashboard.html', {
            'resources': resources,
            'collections': collections
        })
    else:
        # Students see their uploaded files and accessible resources
        student_files = StudentFile.objects.filter(student=request.user).order_by('-upload_date')
        accessible_resources = request.user.accessible_resources.all().order_by('-upload_date')
        
        # Also include resources from enrolled courses
        course_resources = TeacherResource.objects.filter(
            course__in=request.user.enrolled_courses.all(),
            is_public=True
        ).order_by('-upload_date')
        
        # Combine all accessible resources (without duplicates)
        all_resources = list(accessible_resources)
        for resource in course_resources:
            if resource not in all_resources:
                all_resources.append(resource)
        
        collections = ResourceCollection.objects.filter(owner=request.user).order_by('name')
        
        return render(request, 'repository/student_dashboard.html', {
            'student_files': student_files,
            'resources': all_resources,
            'collections': collections
        })

@login_required
def upload_student_file(request):
    """Upload a file (for students)"""
    if not request.user.is_student:
        return redirect('repository:dashboard')
    
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description', '')
        file_type = request.POST.get('file_type')
        
        # Get optional course and lesson if provided
        course_id = request.POST.get('course_id')
        lesson_id = request.POST.get('lesson_id')
        
        course = None
        lesson = None
        
        if course_id:
            try:
                from apps.content.models import Course
                course = Course.objects.get(id=course_id)
                
                # Verify student is enrolled in the course
                if course not in request.user.enrolled_courses.all():
                    course = None
            except:
                course = None
                
        if lesson_id and course:
            try:
                from apps.content.models import Lesson
                lesson = Lesson.objects.get(id=lesson_id, course=course)
            except:
                lesson = None
        
        # Create the file object
        student_file = StudentFile(
            student=request.user,
            title=title,
            description=description,
            file_type=file_type,
            course=course,
            lesson=lesson
        )
        
        # Handle file upload
        if 'file' in request.FILES:
            student_file.file = request.FILES['file']
            student_file.save()
            
            # Add to collection if specified
            collection_id = request.POST.get('collection_id')
            if collection_id:
                try:
                    collection = ResourceCollection.objects.get(id=collection_id, owner=request.user)
                    collection.student_files.add(student_file)
                except:
                    pass
            
            return redirect('repository:dashboard')
        else:
            # No file uploaded
            return render(request, 'repository/upload_file.html', {'error': 'No file was uploaded'})
    
    # GET request
    # Get courses student is enrolled in
    from apps.content.models import Course
    courses = request.user.enrolled_courses.all()
    
    # Get collections
    collections = ResourceCollection.objects.filter(owner=request.user)
    
    return render(request, 'repository/upload_file.html', {
        'courses': courses,
        'collections': collections
    })

@login_required
def upload_teacher_resource(request):
    """Upload a resource (for teachers)"""
    if not request.user.is_teacher:
        return redirect('repository:dashboard')
    
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description', '')
        is_public = request.POST.get('is_public') == 'on'
        
        # Get optional course
        course_id = request.POST.get('course_id')
        course = None
        
        if course_id:
            try:
                from apps.content.models import Course
                course = Course.objects.get(id=course_id, teacher=request.user)
            except:
                course = None
        
        # Create the resource object
        resource = TeacherResource(
            teacher=request.user,
            title=title,
            description=description,
            is_public=is_public,
            course=course
        )
        
        # Handle file upload
        if 'file' in request.FILES:
            resource.file = request.FILES['file']
            resource.save()
            
            # Share with specific students if specified
            student_ids = request.POST.getlist('share_with_students')
            if student_ids:
                from django.contrib.auth.models import User
                for student_id in student_ids:
                    try:
                        student = User.objects.get(id=student_id, is_student=True)
                        resource.shared_with.add(student)
                    except:
                        pass
            
            # Add to collection if specified
            collection_id = request.POST.get('collection_id')
            if collection_id:
                try:
                    collection = ResourceCollection.objects.get(id=collection_id, owner=request.user)
                    collection.resources.add(resource)
                except:
                    pass
            
            return redirect('repository:dashboard')
        else:
            # No file uploaded
            return render(request, 'repository/upload_resource.html', {'error': 'No file was uploaded'})
    
    # GET request
    # Get teacher's courses
    from apps.content.models import Course
    courses = Course.objects.filter(teacher=request.user)
    
    # Get students in teacher's courses
    from django.contrib.auth.models import User
    students = User.objects.filter(
        is_student=True, 
        enrolled_courses__teacher=request.user
    ).distinct()
    
    # Get collections
    collections = ResourceCollection.objects.filter(owner=request.user)
    
    return render(request, 'repository/upload_resource.html', {
        'courses': courses,
        'students': students,
        'collections': collections
    })

@login_required
def download_file(request, file_id):
    """Download a student file"""
    file_obj = get_object_or_404(StudentFile, id=file_id)
    
    # Check permissions
    if file_obj.student != request.user and not request.user.is_teacher:
        return redirect('repository:dashboard')
    
    # Increment view count
    file_obj.increment_view_count()
    
    # Get file path and prepare response
    file_path = file_obj.file.path
    content_type, encoding = mimetypes.guess_type(file_path)
    content_type = content_type or 'application/octet-stream'
    
    # Prepare response
    response = HttpResponse(open(file_path, 'rb'), content_type=content_type)
    response['Content-Disposition'] = f'attachment; filename="{os.path.basename(file_path)}"'
    
    return response

@login_required
def download_resource(request, resource_id):
    """Download a teacher resource"""
    resource = get_object_or_404(TeacherResource, id=resource_id)
    
    # Check permissions
    has_access = False
    
    # Teacher who created it has access
    if request.user == resource.teacher:
        has_access = True
    
    # Students with explicit access
    elif request.user in resource.shared_with.all():
        has_access = True
    
    # Students in the course if resource is public
    elif resource.is_public and resource.course and request.user.is_student:
        if resource.course in request.user.enrolled_courses.all():
            has_access = True
    
    if not has_access:
        return redirect('repository:dashboard')
    
    # Log access if student
    if request.user.is_student:
        ResourceAccess.objects.create(
            resource=resource,
            student=request.user
        )
    
    # Get file path and prepare response
    file_path = resource.file.path
    content_type, encoding = mimetypes.guess_type(file_path)
    content_type = content_type or 'application/octet-stream'
    
    # Prepare response
    response = HttpResponse(open(file_path, 'rb'), content_type=content_type)
    response['Content-Disposition'] = f'attachment; filename="{os.path.basename(file_path)}"'
    
    return response

@login_required
def create_collection(request):
    """Create a new resource collection"""
    if request.method == 'POST':
        name = request.POST.get('name')
        parent_id = request.POST.get('parent_id')
        
        parent = None
        if parent_id:
            try:
                parent = ResourceCollection.objects.get(id=parent_id, owner=request.user)
            except:
                parent = None
        
        collection = ResourceCollection.objects.create(
            name=name,
            owner=request.user,
            parent=parent
        )
        
        return redirect('repository:dashboard')
    
    # GET request
    collections = ResourceCollection.objects.filter(owner=request.user)
    
    return render(request, 'repository/create_collection.html', {'collections': collections})

@login_required
def collection_detail(request, collection_id):
    """View collection contents"""
    collection = get_object_or_404(ResourceCollection, id=collection_id, owner=request.user)
    
    return render(request, 'repository/collection_detail.html', {'collection': collection})

@login_required
def add_to_collection(request):
    """Add files/resources to a collection"""
    if request.method == 'POST':
        collection_id = request.POST.get('collection_id')
        resource_ids = request.POST.getlist('resource_ids')
        file_ids = request.POST.getlist('file_ids')
        
        try:
            collection = ResourceCollection.objects.get(id=collection_id, owner=request.user)
            
            # Add resources
            if resource_ids and request.user.is_teacher:
                for resource_id in resource_ids:
                    try:
                        resource = TeacherResource.objects.get(id=resource_id, teacher=request.user)
                        collection.resources.add(resource)
                    except:
                        pass
            
            # Add student files
            if file_ids and request.user.is_student:
                for file_id in file_ids:
                    try:
                        file_obj = StudentFile.objects.get(id=file_id, student=request.user)
                        collection.student_files.add(file_obj)
                    except:
                        pass
        except:
            pass
        
        return redirect('repository:collection_detail', collection_id=collection_id)
    
    # Redirect to dashboard if GET request
    return redirect('repository:dashboard')