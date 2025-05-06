from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView, View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.contrib import messages
from django.db.models import Count, Q
from web_project import TemplateLayout
from web_project.template_helpers.theme import TemplateHelper
from django.http import JsonResponse
from web_project.ai_services import AIContentService
from django.views import View
from .models import StudentFile, TeacherResource, ResourceAccess, ResourceCollection
from apps.content.models import Course, Lesson
import mimetypes
import json
import os


class RepositoryBaseView(LoginRequiredMixin):
    """Base class for repository views with common template functionality"""
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        # Set active menu attributes for repository section
        context['active_menu'] = 'repository'
        context['active_submenu'] = 'repository-dashboard'
        
        # Set the layout path using TemplateHelper
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context


class RepositoryDashboardView(RepositoryBaseView, TemplateView):
    """Dashboard showing user's files and resources"""
    template_name = 'repostory_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        if hasattr(self.request.user, 'is_teacher') and self.request.user.is_teacher:
            # Teachers see their own uploaded resources
            resources = TeacherResource.objects.filter(teacher=self.request.user).order_by('-upload_date')
            collections = ResourceCollection.objects.filter(owner=self.request.user).order_by('name')
            
            # Add resource statistics
            context['total_resources'] = resources.count()
            context['resource_views'] = ResourceAccess.objects.filter(
                resource__teacher=self.request.user
            ).count()
            
            # Group resources by type
            resource_types = {}
            for resource in resources:
                file_type = self._get_file_type(resource.file.name)
                if file_type not in resource_types:
                    resource_types[file_type] = 0
                resource_types[file_type] += 1
            
            context.update({
                'resources': resources,
                'collections': collections,
                'resource_types': resource_types,
                'is_teacher': True,
                'active_submenu': 'repository-teacher'
            })
        else:
            # Students see their uploaded files and accessible resources
            student_files = StudentFile.objects.filter(student=self.request.user).order_by('-upload_date')
            accessible_resources = self.request.user.accessible_resources.all().order_by('-upload_date')
            
            # Also include resources from enrolled courses
            course_resources = TeacherResource.objects.filter(
                course__in=self.request.user.enrolled_courses.all(),
                is_public=True
            ).order_by('-upload_date')
            
            # Combine all accessible resources (without duplicates)
            all_resources = list(accessible_resources)
            for resource in course_resources:
                if resource not in all_resources:
                    all_resources.append(resource)
            
            collections = ResourceCollection.objects.filter(owner=self.request.user).order_by('name')
            
            # Add file statistics
            context['total_files'] = student_files.count()
            context['total_resources'] = len(all_resources)
            
            context.update({
                'student_files': student_files,
                'resources': all_resources,
                'collections': collections,
                'is_teacher': False,
                'active_submenu': 'repository-student'
            })
        
        return context
    
    def _get_file_type(self, filename):
        """Helper method to get file type from filename"""
        ext = filename.split('.')[-1].lower() if '.' in filename else ''
        
        if ext in ['pdf']:
            return 'PDF'
        elif ext in ['doc', 'docx']:
            return 'Document'
        elif ext in ['xls', 'xlsx']:
            return 'Spreadsheet'
        elif ext in ['ppt', 'pptx']:
            return 'Presentation'
        elif ext in ['jpg', 'jpeg', 'png', 'gif']:
            return 'Image'
        elif ext in ['mp4', 'avi', 'mov', 'webm']:
            return 'Video'
        elif ext in ['mp3', 'wav', 'ogg']:
            return 'Audio'
        else:
            return 'File'


class StudentFileUploadView(RepositoryBaseView, UserPassesTestMixin, CreateView):
    """Upload a file (for students)"""
    model = StudentFile
    template_name = 'upload_file.html'
    fields = ['title', 'description', 'file', 'file_type', 'course', 'lesson']
    success_url = reverse_lazy('repository:dashboard')
    
    def test_func(self):
        return hasattr(self.request.user, 'is_student') and self.request.user.is_student
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        
        # Customize form fields
        form.fields['file_type'].widget.attrs.update({'class': 'form-control'})
        form.fields['description'].widget.attrs.update({'class': 'form-control', 'rows': 3})
        
        # Filter courses to only show enrolled courses
        form.fields['course'].queryset = self.request.user.enrolled_courses.all()
        form.fields['course'].required = False
        
        # Lesson field will be populated via AJAX based on selected course
        form.fields['lesson'].queryset = Lesson.objects.none()
        form.fields['lesson'].required = False
        
        return form
    
    def form_valid(self, form):
        # Set student to current user
        form.instance.student = self.request.user
        
        # Save the file
        response = super().form_valid(form)
        
        # Add to collection if specified
        collection_id = self.request.POST.get('collection_id')
        if collection_id:
            try:
                collection = ResourceCollection.objects.get(id=collection_id, owner=self.request.user)
                collection.student_files.add(self.object)
            except ResourceCollection.DoesNotExist:
                pass
        
        messages.success(self.request, f"File '{self.object.title}' uploaded successfully.")
        return response
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add collections for selection
        context['collections'] = ResourceCollection.objects.filter(owner=self.request.user)
        context['active_submenu'] = 'repository-upload'
        context['title'] = 'Upload File'
        
        return context


class TeacherResourceUploadView(RepositoryBaseView, UserPassesTestMixin, CreateView):
    """Upload a resource (for teachers)"""
    model = TeacherResource
    template_name = 'upload_resource.html'
    fields = ['title', 'description', 'file', 'is_public', 'course']
    success_url = reverse_lazy('repository:dashboard')
    
    def test_func(self):
        return hasattr(self.request.user, 'is_teacher') and self.request.user.is_teacher
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        
        # Customize form fields
        form.fields['description'].widget.attrs.update({'class': 'form-control', 'rows': 3})
        
        # Filter courses to only show courses taught by this teacher
        form.fields['course'].queryset = Course.objects.filter(teacher=self.request.user)
        form.fields['course'].required = False
        
        return form
    
    def form_valid(self, form):
        # Set teacher to current user
        form.instance.teacher = self.request.user
        
        # Save the resource
        response = super().form_valid(form)
        
        # Share with specific students if specified
        student_ids = self.request.POST.getlist('share_with_students')
        if student_ids:
            from django.contrib.auth.models import User
            for student_id in student_ids:
                try:
                    student = User.objects.get(id=student_id, is_student=True)
                    self.object.shared_with.add(student)
                except User.DoesNotExist:
                    pass
        
        # Add to collection if specified
        collection_id = self.request.POST.get('collection_id')
        if collection_id:
            try:
                collection = ResourceCollection.objects.get(id=collection_id, owner=self.request.user)
                collection.resources.add(self.object)
            except ResourceCollection.DoesNotExist:
                pass
        
        messages.success(self.request, f"Resource '{self.object.title}' uploaded successfully.")
        return response
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get students from teacher's courses
        from django.contrib.auth.models import User
        students = User.objects.filter(
            is_student=True, 
            enrolled_courses__teacher=self.request.user
        ).distinct()
        
        # Add collections for selection
        context['collections'] = ResourceCollection.objects.filter(owner=self.request.user)
        context['students'] = students
        context['active_submenu'] = 'repository-upload'
        context['title'] = 'Upload Resource'
        
        return context


class StudentFileDetailView(RepositoryBaseView, DetailView):
    """View details of a student file"""
    model = StudentFile
    template_name = 'file_detail.html'
    context_object_name = 'file'
    pk_url_kwarg = 'file_id'
    
    def get(self, request, *args, **kwargs):
        file_obj = self.get_object()
        
        # Check permissions
        if file_obj.student != request.user and not request.user.is_teacher:
            messages.error(request, "You don't have permission to view this file.")
            return redirect('repository:dashboard')
        
        # Increment view count
        file_obj.increment_view_count()
        
        return super().get(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'File: {self.object.title}'
        return context


class ResourceDetailView(RepositoryBaseView, DetailView):
    """View details of a teacher resource"""
    model = TeacherResource
    template_name = 'resource_detail.html'
    context_object_name = 'resource'
    pk_url_kwarg = 'resource_id'
    
    def get(self, request, *args, **kwargs):
        resource = self.get_object()
        
        # Check permissions
        has_access = False
        
        # Teacher who created it has access
        if request.user == resource.teacher:
            has_access = True
        
        # Students with explicit access
        elif request.user in resource.shared_with.all():
            has_access = True
        
        # Students in the course if resource is public
        elif resource.is_public and resource.course and hasattr(request.user, 'is_student') and request.user.is_student:
            if resource.course in request.user.enrolled_courses.all():
                has_access = True
        
        if not has_access:
            messages.error(request, "You don't have permission to view this resource.")
            return redirect('repository:dashboard')
        
        # Log access if student
        if hasattr(request.user, 'is_student') and request.user.is_student:
            ResourceAccess.objects.create(
                resource=resource,
                student=request.user
            )
        
        return super().get(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Resource: {self.object.title}'
        
        # If teacher, show access stats
        if hasattr(self.request.user, 'is_teacher') and self.request.user.is_teacher:
            access_logs = ResourceAccess.objects.filter(resource=self.object).order_by('-access_time')
            context['access_logs'] = access_logs[:20]  # Show last 20 accesses
            context['access_count'] = access_logs.count()
            
            # Group by student
            student_access = {}
            for log in access_logs:
                if log.student.id not in student_access:
                    student_access[log.student.id] = {
                        'student': log.student,
                        'count': 0,
                        'last_access': None
                    }
                student_access[log.student.id]['count'] += 1
                if not student_access[log.student.id]['last_access'] or log.access_time > student_access[log.student.id]['last_access']:
                    student_access[log.student.id]['last_access'] = log.access_time
            
            context['student_access'] = list(student_access.values())
        
        return context


class FileDownloadView(LoginRequiredMixin, View):
    """Download a student file"""
    def get(self, request, file_id):
        file_obj = get_object_or_404(StudentFile, id=file_id)
        
        # Check permissions
        if file_obj.student != request.user and not request.user.is_teacher:
            messages.error(request, "You don't have permission to download this file.")
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


class ResourceDownloadView(LoginRequiredMixin, View):
    """Download a teacher resource"""
    def get(self, request, resource_id):
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
        elif resource.is_public and resource.course and hasattr(request.user, 'is_student') and request.user.is_student:
            if resource.course in request.user.enrolled_courses.all():
                has_access = True
        
        if not has_access:
            messages.error(request, "You don't have permission to download this resource.")
            return redirect('repository:dashboard')
        
        # Log access if student
        if hasattr(request.user, 'is_student') and request.user.is_student:
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


class CollectionCreateView(RepositoryBaseView, CreateView):
    """Create a new resource collection"""
    model = ResourceCollection
    template_name = 'create_collection.html'
    fields = ['name', 'parent']
    success_url = reverse_lazy('repository:dashboard')
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        
        # Filter parent collections to only show user's collections
        form.fields['parent'].queryset = ResourceCollection.objects.filter(owner=self.request.user)
        form.fields['parent'].required = False
        
        return form
    
    def form_valid(self, form):
        # Set owner to current user
        form.instance.owner = self.request.user
        
        messages.success(self.request, f"Collection '{form.instance.name}' created successfully.")
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Create Collection'
        context['active_submenu'] = 'repository-collections'
        return context


class CollectionDetailView(RepositoryBaseView, DetailView):
    """View collection contents"""
    model = ResourceCollection
    template_name = 'collection_detail.html'
    context_object_name = 'collection'
    pk_url_kwarg = 'collection_id'
    
    def get(self, request, *args, **kwargs):
        collection = self.get_object()
        
        # Check permissions
        if collection.owner != request.user:
            messages.error(request, "You don't have permission to view this collection.")
            return redirect('repository:dashboard')
        
        return super().get(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Collection: {self.object.name}'
        context['active_submenu'] = 'repository-collections'
        
        # Get subcollections
        context['subcollections'] = ResourceCollection.objects.filter(parent=self.object)
        
        return context


class AddToCollectionView(RepositoryBaseView, View):
    """Add files/resources to a collection"""
    def post(self, request):
        collection_id = request.POST.get('collection_id')
        resource_ids = request.POST.getlist('resource_ids')
        file_ids = request.POST.getlist('file_ids')
        
        try:
            collection = ResourceCollection.objects.get(id=collection_id, owner=request.user)
            
            # Add resources
            if resource_ids and hasattr(request.user, 'is_teacher') and request.user.is_teacher:
                for resource_id in resource_ids:
                    try:
                        resource = TeacherResource.objects.get(id=resource_id, teacher=request.user)
                        collection.resources.add(resource)
                    except TeacherResource.DoesNotExist:
                        pass
            
            # Add student files
            if file_ids and hasattr(request.user, 'is_student') and request.user.is_student:
                for file_id in file_ids:
                    try:
                        file_obj = StudentFile.objects.get(id=file_id, student=request.user)
                        collection.student_files.add(file_obj)
                    except StudentFile.DoesNotExist:
                        pass
                        
            messages.success(request, "Items added to collection successfully.")
        except ResourceCollection.DoesNotExist:
            messages.error(request, "Collection not found.")
        
        return redirect('repository:collection_detail', collection_id=collection_id)


class RemoveFromCollectionView(RepositoryBaseView, View):
    """Remove files/resources from a collection"""
    def post(self, request):
        collection_id = request.POST.get('collection_id')
        resource_id = request.POST.get('resource_id')
        file_id = request.POST.get('file_id')
        
        try:
            collection = ResourceCollection.objects.get(id=collection_id, owner=request.user)
            
            # Remove resource
            if resource_id:
                try:
                    resource = TeacherResource.objects.get(id=resource_id)
                    collection.resources.remove(resource)
                    messages.success(request, f"Resource removed from collection.")
                except TeacherResource.DoesNotExist:
                    messages.error(request, "Resource not found.")
            
            # Remove file
            if file_id:
                try:
                    file_obj = StudentFile.objects.get(id=file_id)
                    collection.student_files.remove(file_obj)
                    messages.success(request, f"File removed from collection.")
                except StudentFile.DoesNotExist:
                    messages.error(request, "File not found.")
                    
        except ResourceCollection.DoesNotExist:
            messages.error(request, "Collection not found.")
        
        return redirect('repository:collection_detail', collection_id=collection_id)


class StudentFilesListView(RepositoryBaseView, ListView):
    """List all student files"""
    model = StudentFile
    template_name = 'student_files_list.html'
    context_object_name = 'files'
    paginate_by = 10
    
    def get_queryset(self):
        # Students see only their own files
        if hasattr(self.request.user, 'is_student') and self.request.user.is_student:
            queryset = StudentFile.objects.filter(student=self.request.user)
        # Teachers see files from their students
        elif hasattr(self.request.user, 'is_teacher') and self.request.user.is_teacher:
            student_ids = self.request.user.course_set.values_list('students', flat=True)
            queryset = StudentFile.objects.filter(student_id__in=student_ids)
        else:
            queryset = StudentFile.objects.none()
            
        # Apply filters
        course_id = self.request.GET.get('course')
        if course_id:
            queryset = queryset.filter(course_id=course_id)
            
        file_type = self.request.GET.get('file_type')
        if file_type:
            queryset = queryset.filter(file_type=file_type)
            
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(Q(title__icontains=search) | Q(description__icontains=search))
            
        return queryset.order_by('-upload_date')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'My Files' if self.request.user.is_student else 'Student Files'
        context['active_submenu'] = 'repository-files'
        
        # Add filter options
        if self.request.user.is_student:
            context['courses'] = self.request.user.enrolled_courses.all()
        else:
            context['courses'] = Course.objects.filter(teacher=self.request.user)
            
        context['file_types'] = StudentFile.objects.values_list('file_type', flat=True).distinct()
        
        return context


class TeacherResourcesListView(RepositoryBaseView, ListView):
    """List all teacher resources"""
    model = TeacherResource
    template_name = 'teacher_resources_list.html'
    context_object_name = 'resources'
    paginate_by = 10
    
    def get_queryset(self):
        # Teachers see their own resources
        if hasattr(self.request.user, 'is_teacher') and self.request.user.is_teacher:
            queryset = TeacherResource.objects.filter(teacher=self.request.user)
        # Students see resources shared with them or from their courses
        elif hasattr(self.request.user, 'is_student') and self.request.user.is_student:
            # Get directly shared resources
            shared_resources = self.request.user.accessible_resources.all()
            
            # Get resources from enrolled courses that are public
            course_resources = TeacherResource.objects.filter(
                course__in=self.request.user.enrolled_courses.all(),
                is_public=True
            )
            
            # Combine querysets
            queryset = shared_resources | course_resources
        else:
            queryset = TeacherResource.objects.none()
            
        # Apply filters
        course_id = self.request.GET.get('course')
        if course_id:
            queryset = queryset.filter(course_id=course_id)
            
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(Q(title__icontains=search) | Q(description__icontains=search))
            
        return queryset.order_by('-upload_date')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'My Resources' if self.request.user.is_teacher else 'Learning Resources'
        context['active_submenu'] = 'repository-resources'
        
        # Add filter options
        if self.request.user.is_teacher:
            context['courses'] = Course.objects.filter(teacher=self.request.user)
        else:
            context['courses'] = self.request.user.enrolled_courses.all()
            
        return context


class StudentFileEditView(RepositoryBaseView, UserPassesTestMixin, UpdateView):
    """Edit a student file"""
    model = StudentFile
    template_name = 'edit_file.html'
    fields = ['title', 'description', 'course', 'lesson']
    pk_url_kwarg = 'file_id'
    
    def test_func(self):
        file_obj = self.get_object()
        return file_obj.student == self.request.user
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        
        # Filter courses to only show enrolled courses
        form.fields['course'].queryset = self.request.user.enrolled_courses.all()
        form.fields['course'].required = False
        
        # Filter lessons based on selected course
        if self.object.course:
            form.fields['lesson'].queryset = Lesson.objects.filter(course=self.object.course)
        else:
            form.fields['lesson'].queryset = Lesson.objects.none()
        form.fields['lesson'].required = False
        
        return form
    
    def get_success_url(self):
        return reverse('repository:file_detail', kwargs={'file_id': self.object.id})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Edit File: {self.object.title}'
        context['active_submenu'] = 'repository-files'
        return context


class TeacherResourceEditView(RepositoryBaseView, UserPassesTestMixin, UpdateView):
    """Edit a teacher resource"""
    model = TeacherResource
    template_name = 'edit_resource.html'
    fields = ['title', 'description', 'is_public', 'course']
    pk_url_kwarg = 'resource_id'
    
    def test_func(self):
        resource = self.get_object()
        return resource.teacher == self.request.user
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        
        # Filter courses to only show courses taught by this teacher
        form.fields['course'].queryset = Course.objects.filter(teacher=self.request.user)
        form.fields['course'].required = False
        
        return form
    
    def form_valid(self, form):
        # Update shared_with if provided
        self.object = form.save()
        
        student_ids = self.request.POST.getlist('share_with_students')
        if student_ids:
            # Clear existing shares
            self.object.shared_with.clear()
            
            # Add new shares
            from django.contrib.auth.models import User
            for student_id in student_ids:
                try:
                    student = User.objects.get(id=student_id, is_student=True)
                    self.object.shared_with.add(student)
                except User.DoesNotExist:
                    pass
        
        messages.success(self.request, f"Resource '{self.object.title}' updated successfully.")
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('repository:resource_detail', kwargs={'resource_id': self.object.id})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get students from teacher's courses
        from django.contrib.auth.models import User
        students = User.objects.filter(
            is_student=True, 
            enrolled_courses__teacher=self.request.user
        ).distinct()
        
        # Get currently shared students
        shared_with = self.object.shared_with.all()
        
        context.update({
            'title': f'Edit Resource: {self.object.title}',
            'active_submenu': 'repository-resources',
            'students': students,
            'shared_with': shared_with
        })
        
        return context


class TextRewriteView(LoginRequiredMixin, View):
    """View for rewriting text using AI"""
    
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            text = data.get('text', '')
            style = data.get('style', None)
            
            if not text:
                return JsonResponse({'success': False, 'message': 'Text is required'})
                
            # Rewrite text using AI service
            result = AIContentService.rewrite_text(text, style)
            
            return JsonResponse(result)
            
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': 'Invalid JSON data'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})        