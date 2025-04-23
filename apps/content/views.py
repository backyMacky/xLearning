from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View, TemplateView, RedirectView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.http import Http404, HttpResponseRedirect, JsonResponse
from django.contrib import messages
from django.db import models
from django.db.models import Q, Count, Avg, Max, Value, CharField
from django.utils import timezone
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from web_project import TemplateLayout
from web_project.template_helpers.theme import TemplateHelper

from .models import (
    Course, LearningModule, Lesson, PrivateSession, GroupSession,
    Resource, Instructor, InstructorReview, LessonCompletion,
    CourseProgress, SessionFeedback
)

from .forms import (
    CourseForm, ModuleForm, LessonForm, CourseFilterForm,
    ResourceForm, ResourceFilterForm, InstructorProfileForm, 
    PrivateSessionForm, GroupSessionForm, SessionFeedbackForm,
    InstructorReviewForm
)


class CourseListView(ListView):
    """View to list all available courses with filtering options"""
    model = Course
    context_object_name = 'courses'
    template_name = 'course_list.html'
    paginate_by = 12
    
    def get_queryset(self):
        queryset = Course.objects.filter(is_published=True)
        
        # Get filter form from GET parameters
        form = CourseFilterForm(self.request.GET)
        if form.is_valid():
            # Filter by language
            language = form.cleaned_data.get('language')
            if language:
                queryset = queryset.filter(language=language)
            
            # Filter by level
            level = form.cleaned_data.get('level')
            if level:
                queryset = queryset.filter(level=level)
            
            # Search by title or description
            search_query = form.cleaned_data.get('q')
            if search_query:
                queryset = queryset.filter(
                    Q(title__icontains=search_query) | 
                    Q(description__icontains=search_query)
                )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        # Add filter form to context
        context['filter_form'] = CourseFilterForm(self.request.GET)
        
        # Get featured courses
        context['featured_courses'] = Course.objects.filter(
            is_published=True, 
            is_featured=True
        )[:4]
        
        # Set active menu attributes
        context['active_menu'] = 'content'
        context['active_submenu'] = 'courses'
        
        # Set the layout path
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context


class CourseDetailView(DetailView):
    """View to display course details and manage enrollment"""
    model = Course
    context_object_name = 'course'
    template_name = 'course_detail.html'
    
    def get_object(self, queryset=None):
        # Get course by slug
        slug = self.kwargs.get('slug')
        course = get_object_or_404(Course, slug=slug)
        
        # Only allow access to published courses or if user is the teacher
        if not course.is_published and not self.request.user == course.teacher:
            if not self.request.user.is_superuser:
                raise Http404("Course not found")
        
        return course
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        course = self.get_object()
        
        # Check if user is enrolled
        if self.request.user.is_authenticated:
            context['is_enrolled'] = self.request.user in course.students.all()
        
        # Get all modules and lessons
        context['modules'] = course.modules.all().order_by('order')
        
        # Get student progress if enrolled
        if self.request.user.is_authenticated and context.get('is_enrolled'):
            progress, created = CourseProgress.objects.get_or_create(
                student=self.request.user,
                course=course
            )
            context['progress'] = progress
            
            # Get completed lessons for this user
            completed_lessons = LessonCompletion.objects.filter(
                student=self.request.user,
                lesson__module__course=course
            ).values_list('lesson_id', flat=True)
            
            context['completed_lessons'] = completed_lessons
        
        # Get course resources
        context['resources'] = Resource.objects.filter(
            Q(course=course) & (Q(is_public=True) | Q(created_by=self.request.user))
        )
        
        # Set active menu attributes
        context['active_menu'] = 'content'
        context['active_submenu'] = 'courses'
        
        # Set the layout path
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context
    
    def post(self, request, *args, **kwargs):
        """Handle enrollment/unenrollment"""
        course = self.get_object()
        action = request.POST.get('action')
        
        if not request.user.is_authenticated:
            messages.error(request, "Please log in to enroll in courses.")
            return redirect('account:login')
        
        if action == 'enroll':
            # Enroll student in course
            if request.user in course.students.all():
                messages.info(request, "You are already enrolled in this course.")
            else:
                course.add_student(request.user)
                messages.success(request, f"You have successfully enrolled in {course.title}.")
        
        elif action == 'unenroll':
            # Unenroll student from course
            if request.user in course.students.all():
                course.remove_student(request.user)
                messages.success(request, f"You have been unenrolled from {course.title}.")
            else:
                messages.info(request, "You are not enrolled in this course.")
        
        return redirect('content:course_detail', slug=course.slug)


class CreateCourseView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """View for teachers to create courses"""
    model = Course
    form_class = CourseForm
    template_name = 'course_form.html'
    
    def test_func(self):
        """Only teachers can create courses"""
        return self.request.user.is_superuser or hasattr(self.request.user, 'instructor_profile')
    
    def form_valid(self, form):
        # Set the teacher to the current user
        form.instance.teacher = self.request.user
        messages.success(self.request, "Course created successfully!")
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        context['title'] = 'Create New Course'
        context['submit_text'] = 'Create Course'
        
        # Set active menu attributes
        context['active_menu'] = 'content'
        context['active_submenu'] = 'courses'
        
        # Set the layout path
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context


class UpdateCourseView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """View for teachers to update courses"""
    model = Course
    form_class = CourseForm
    template_name = 'course_form.html'
    
    def test_func(self):
        """Only the course teacher or superuser can update"""
        course = self.get_object()
        return self.request.user.is_superuser or self.request.user == course.teacher
    
    def form_valid(self, form):
        messages.success(self.request, "Course updated successfully!")
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        context['title'] = f'Edit Course: {self.object.title}'
        context['submit_text'] = 'Update Course'
        
        # Get course modules
        context['modules'] = self.object.modules.all().order_by('order')
        
        # Set active menu attributes
        context['active_menu'] = 'content'
        context['active_submenu'] = 'courses'
        
        # Set the layout path
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context


class CreateModuleView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """View for creating modules within a course"""
    model = LearningModule
    form_class = ModuleForm
    template_name = 'module_form.html'
    
    def setup(self, request, *args, **kwargs):
        """Get the course from URL"""
        super().setup(request, *args, **kwargs)
        self.course = get_object_or_404(Course, id=kwargs.get('course_id'))
    
    def test_func(self):
        """Only the course teacher or superuser can add modules"""
        return self.request.user.is_superuser or self.request.user == self.course.teacher
    
    def form_valid(self, form):
        # Set the course for this module
        form.instance.course = self.course
        
        # If no order specified, put at the end
        if not form.instance.order:
            max_order = self.course.modules.aggregate(max_order=models.Max('order'))['max_order'] or 0
            form.instance.order = max_order + 1
        
        messages.success(self.request, "Module created successfully!")
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('content:course_detail', kwargs={'slug': self.course.slug})
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        context['title'] = f'Add Module to {self.course.title}'
        context['course'] = self.course
        context['submit_text'] = 'Create Module'
        
        # Set active menu attributes
        context['active_menu'] = 'content'
        context['active_submenu'] = 'courses'
        
        # Set the layout path
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context


class UpdateModuleView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """View for updating modules"""
    model = LearningModule
    form_class = ModuleForm
    template_name = 'module_form.html'
    pk_url_kwarg = 'module_id'
    
    def test_func(self):
        """Only the course teacher or superuser can update modules"""
        module = self.get_object()
        return self.request.user.is_superuser or self.request.user == module.course.teacher
    
    def form_valid(self, form):
        messages.success(self.request, "Module updated successfully!")
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('content:course_detail', kwargs={'slug': self.object.course.slug})
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        context['title'] = f'Edit Module: {self.object.title}'
        context['course'] = self.object.course
        context['submit_text'] = 'Update Module'
        
        # Set active menu attributes
        context['active_menu'] = 'content'
        context['active_submenu'] = 'courses'
        
        # Set the layout path
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context


class DeleteModuleView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """View for deleting modules"""
    model = LearningModule
    template_name = 'confirm_delete.html'
    pk_url_kwarg = 'module_id'
    
    def test_func(self):
        """Only the course teacher or superuser can delete modules"""
        module = self.get_object()
        return self.request.user.is_superuser or self.request.user == module.course.teacher
    
    def get_success_url(self):
        return reverse('content:course_detail', kwargs={'slug': self.object.course.slug})
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        context['title'] = f'Delete Module: {self.object.title}'
        context['message'] = 'Are you sure you want to delete this module? This will also delete all lessons within this module.'
        context['back_url'] = reverse('content:course_detail', kwargs={'slug': self.object.course.slug})
        
        # Set active menu attributes
        context['active_menu'] = 'content'
        context['active_submenu'] = 'courses'
        
        # Set the layout path
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context
    
    def delete(self, request, *args, **kwargs):
        module = self.get_object()
        course_slug = module.course.slug
        
        # Delete all lessons in the module
        module.lessons.all().delete()
        
        # Delete the module
        module.delete()
        
        messages.success(request, "Module and all its lessons have been deleted.")
        return redirect('content:course_detail', slug=course_slug)


class CreateLessonView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """View for creating lessons within a module"""
    model = Lesson
    form_class = LessonForm
    template_name = 'lesson_form.html'
    
    def setup(self, request, *args, **kwargs):
        """Get the module from URL"""
        super().setup(request, *args, **kwargs)
        self.module = get_object_or_404(LearningModule, id=kwargs.get('module_id'))
    
    def test_func(self):
        """Only the course teacher or superuser can add lessons"""
        return self.request.user.is_superuser or self.request.user == self.module.course.teacher
    
    def form_valid(self, form):
        # Set the module for this lesson
        form.instance.module = self.module
        
        # If no order specified, put at the end
        if not form.instance.order:
            max_order = self.module.lessons.aggregate(max_order=models.Max('order'))['max_order'] or 0
            form.instance.order = max_order + 1
        
        # Save form first
        response = super().form_valid(form)
        
        # Generate keywords from content
        form.generate_keywords()
        
        messages.success(self.request, "Lesson created successfully!")
        return response
    
    def get_success_url(self):
        return reverse('content:course_detail', kwargs={'slug': self.module.course.slug})
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        context['title'] = f'Add Lesson to {self.module.title}'
        context['module'] = self.module
        context['submit_text'] = 'Create Lesson'
        
        # Set active menu attributes
        context['active_menu'] = 'content'
        context['active_submenu'] = 'courses'
        
        # Set the layout path
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context


class UpdateLessonView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """View for updating lessons"""
    model = Lesson
    form_class = LessonForm
    template_name = 'lesson_form.html'
    slug_url_kwarg = 'lesson_slug'
    
    def test_func(self):
        """Only the course teacher or superuser can update lessons"""
        lesson = self.get_object()
        return self.request.user.is_superuser or self.request.user == lesson.module.course.teacher
    
    def form_valid(self, form):
        # Save form first
        response = super().form_valid(form)
        
        # Generate keywords from content
        form.generate_keywords()
        
        messages.success(self.request, "Lesson updated successfully!")
        return response
    
    def get_success_url(self):
        return reverse('content:lesson_detail', kwargs={
            'course_slug': self.object.module.course.slug,
            'lesson_slug': self.object.slug
        })
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        context['title'] = f'Edit Lesson: {self.object.title}'
        context['module'] = self.object.module
        context['submit_text'] = 'Update Lesson'
        
        # Set active menu attributes
        context['active_menu'] = 'content'
        context['active_submenu'] = 'courses'
        
        # Set the layout path
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context


class DeleteLessonView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """View for deleting lessons"""
    model = Lesson
    template_name = 'confirm_delete.html'
    slug_url_kwarg = 'lesson_slug'
    
    def test_func(self):
        """Only the course teacher or superuser can delete lessons"""
        lesson = self.get_object()
        return self.request.user.is_superuser or self.request.user == lesson.module.course.teacher
    
    def get_success_url(self):
        return reverse('content:course_detail', kwargs={'slug': self.object.module.course.slug})
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        context['title'] = f'Delete Lesson: {self.object.title}'
        context['message'] = 'Are you sure you want to delete this lesson?'
        context['back_url'] = reverse('content:lesson_detail', kwargs={
            'course_slug': self.object.module.course.slug,
            'lesson_slug': self.object.slug
        })
        
        # Set active menu attributes
        context['active_menu'] = 'content'
        context['active_submenu'] = 'courses'
        
        # Set the layout path
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context


class LessonDetailView(DetailView):
    """View to display lesson contents and track progress"""
    model = Lesson
    context_object_name = 'lesson'
    template_name = 'lesson_detail.html'
    slug_url_kwarg = 'lesson_slug'
    
    def get_object(self, queryset=None):
        # Get course and lesson slugs from URL
        course_slug = self.kwargs.get('course_slug')
        lesson_slug = self.kwargs.get('lesson_slug')
        
        # Get the lesson
        lesson = get_object_or_404(
            Lesson,
            slug=lesson_slug,
            module__course__slug=course_slug
        )
        
        # Check if user has access to this lesson
        course = lesson.module.course
        if not course.is_published and self.request.user != course.teacher:
            if not self.request.user.is_superuser:
                raise Http404("Lesson not found")
        
        # If user is not enrolled or teacher, prevent access
        if not (self.request.user == course.teacher or 
                self.request.user.is_superuser or
                self.request.user in course.students.all()):
            raise Http404("You need to enroll in this course to access lessons")
        
        return lesson
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        lesson = self.get_object()
        course = lesson.module.course
        
        # Add course to context
        context['course'] = course
        
        # Get prev/next lessons
        # First try to get the previous lesson in same module
        prev_lessons = Lesson.objects.filter(
            module=lesson.module,
            order__lt=lesson.order
        ).order_by('-order')
        
        if prev_lessons.exists():
            context['prev_lesson'] = prev_lessons.first()
        else:
            # Try to get the last lesson of the previous module
            prev_modules = LearningModule.objects.filter(
                course=course,
                order__lt=lesson.module.order
            ).order_by('-order')
            
            if prev_modules.exists():
                prev_module = prev_modules.first()
                last_lesson = prev_module.lessons.order_by('-order').first()
                if last_lesson:
                    context['prev_lesson'] = last_lesson
        
        # Get next lesson
        context['next_lesson'] = lesson.get_next_lesson()
        
        # Get student progress if enrolled
        if self.request.user.is_authenticated and self.request.user in course.students.all():
            # Get completed lessons for this user
            completed_lessons = LessonCompletion.objects.filter(
                student=self.request.user,
                lesson__module__course=course
            ).values_list('lesson_id', flat=True)
            
            context['completed_lessons'] = completed_lessons
            
            # Calculate progress percentage
            total_lessons = Lesson.objects.filter(module__course=course).count()
            if total_lessons > 0:
                context['progress_percentage'] = (len(completed_lessons) / total_lessons) * 100
            else:
                context['progress_percentage'] = 0
        
        # Set active menu attributes
        context['active_menu'] = 'content'
        context['active_submenu'] = 'courses'
        
        # Set the layout path
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context


@login_required
def mark_lesson_complete(request, lesson_id):
    """View to mark lessons as complete/incomplete for students"""
    if not request.method == 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=400)
    
    lesson = get_object_or_404(Lesson, id=lesson_id)
    course = lesson.module.course
    
    # Check if student is enrolled in the course
    if course not in request.user.enrolled_courses.all():
        return JsonResponse({'error': 'You are not enrolled in this course'}, status=403)
    
    # Get or create course progress
    progress, created = CourseProgress.objects.get_or_create(
        student=request.user,
        course=course
    )
    
    action = request.POST.get('action', 'complete')
    
    if action == 'complete':
        # Mark lesson as complete
        completion, created = LessonCompletion.objects.get_or_create(
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


class ResourceListView(ListView):
    """View to list all educational resources with filtering"""
    model = Resource
    context_object_name = 'resources'
    template_name = 'resource_list.html'
    paginate_by = 12
    
    def get_queryset(self):
        queryset = Resource.objects.all()
        
        # Non-admin users can only see public resources or their own
        if not self.request.user.is_superuser and not self.request.user.is_staff:
            queryset = queryset.filter(
                Q(is_public=True) | Q(created_by=self.request.user)
            )
        
        # Apply filters from form
        form = ResourceFilterForm(self.request.GET)
        if form.is_valid():
            # Filter by language
            language = form.cleaned_data.get('language')
            if language:
                queryset = queryset.filter(language=language)
            
            # Filter by level
            level = form.cleaned_data.get('level')
            if level:
                queryset = queryset.filter(level=level)
            
            # Filter by resource type
            resource_type = form.cleaned_data.get('resource_type')
            if resource_type:
                queryset = queryset.filter(resource_type=resource_type)
            
            # Search by title or description
            search_query = form.cleaned_data.get('q')
            if search_query:
                queryset = queryset.filter(
                    Q(title__icontains=search_query) | 
                    Q(description__icontains=search_query) |
                    Q(tags__icontains=search_query)
                )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        # Add filter form to context
        context['filter_form'] = ResourceFilterForm(self.request.GET)
        
        # Set active menu attributes
        context['active_menu'] = 'content'
        context['active_submenu'] = 'resources'
        
        # Set the layout path
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context


class CreateResourceView(LoginRequiredMixin, CreateView):
    """View for creating educational resources"""
    model = Resource
    form_class = ResourceForm
    template_name = 'resource_form.html'
    success_url = reverse_lazy('content:resource_list')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, "Resource created successfully!")
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        context['title'] = 'Create Educational Resource'
        context['submit_text'] = 'Create Resource'
        
        # Set active menu attributes
        context['active_menu'] = 'content'
        context['active_submenu'] = 'resources'
        
        # Set the layout path
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context


class UpdateResourceView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """View for updating educational resources"""
    model = Resource
    form_class = ResourceForm
    template_name = 'resource_form.html'
    pk_url_kwarg = 'resource_id'
    success_url = reverse_lazy('content:resource_list')
    
    def test_func(self):
        """Only the creator, superuser, or staff can update resources"""
        resource = self.get_object()
        return (self.request.user.is_superuser or 
                self.request.user.is_staff or 
                self.request.user == resource.created_by)
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        messages.success(self.request, "Resource updated successfully!")
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        context['title'] = 'Edit Resource'
        context['submit_text'] = 'Update Resource'
        
        # Set active menu attributes
        context['active_menu'] = 'content'
        context['active_submenu'] = 'resources'
        
        # Set the layout path
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context


class DeleteResourceView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """View for deleting educational resources"""
    model = Resource
    template_name = 'confirm_delete.html'
    pk_url_kwarg = 'resource_id'
    success_url = reverse_lazy('content:resource_list')
    
    def test_func(self):
        """Only the creator, superuser, or staff can delete resources"""
        resource = self.get_object()
        return (self.request.user.is_superuser or 
                self.request.user.is_staff or 
                self.request.user == resource.created_by)
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        context['title'] = f'Delete Resource: {self.object.title}'
        context['message'] = 'Are you sure you want to delete this resource?'
        context['back_url'] = reverse('content:resource_list')
        
        # Set active menu attributes
        context['active_menu'] = 'content'
        context['active_submenu'] = 'resources'
        
        # Set the layout path
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context


class InstructorListView(ListView):
    """View to list all available instructors with filtering options"""
    model = Instructor
    context_object_name = 'instructors'
    template_name = 'instructor_list.html'
    paginate_by = 12
    
    def get_queryset(self):
        queryset = Instructor.objects.filter(is_available=True).select_related('user')
        
        # Filter by language
        language = self.request.GET.get('language')
        if language:
            queryset = queryset.filter(teaching_languages__contains=language)
        
        # Filter by specialty
        specialty = self.request.GET.get('specialty')
        if specialty:
            queryset = queryset.filter(specialties__contains=specialty)
        
        # Search by name or bio
        search_query = self.request.GET.get('q')
        if search_query:
            queryset = queryset.filter(
                Q(user__username__icontains=search_query) | 
                Q(bio__icontains=search_query) |
                Q(teaching_style__icontains=search_query)
            )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        # Add language and specialty options for filtering
        context['language_choices'] = dict(Course.LANGUAGE_CHOICES)
        context['specialty_choices'] = dict(Instructor.SPECIALTY_CHOICES)
        
        # Set selected filter values
        context['selected_language'] = self.request.GET.get('language', '')
        context['selected_specialty'] = self.request.GET.get('specialty', '')
        context['search_query'] = self.request.GET.get('q', '')
        
        # Add featured instructors
        context['featured_instructors'] = Instructor.objects.filter(
            is_featured=True, 
            is_available=True
        ).select_related('user')[:4]
        
        # Set active menu attributes
        context['active_menu'] = 'content'
        context['active_submenu'] = 'instructors'
        
        # Set the layout path
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context


class InstructorDetailView(DetailView):
    """View to display instructor profile and available booking slots"""
    model = Instructor
    context_object_name = 'instructor'
    template_name = 'instructor_detail.html'
    slug_field = 'user__username'
    slug_url_kwarg = 'username'
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        instructor = self.get_object()
        
        # Get available private session slots
        now = timezone.now()
        context['available_slots'] = PrivateSession.objects.filter(
            instructor=instructor,
            status='available',
            start_time__gt=now
        ).order_by('start_time')
        
        # Add today's date for the calendar
        context['today'] = now.date()
        
        # Get upcoming group sessions by this instructor
        context['group_sessions'] = GroupSession.objects.filter(
            instructor=instructor,
            status='scheduled',
            start_time__gt=now
        ).order_by('start_time')
        
        # Mark group sessions the user is enrolled in
        if self.request.user.is_authenticated:
            for session in context['group_sessions']:
                session.is_enrolled = self.request.user in session.students.all()
        
        # Get instructor reviews
        context['reviews'] = InstructorReview.objects.filter(
            instructor=instructor
        ).select_related('student').order_by('-created_at')[:3]
        
        context['review_count'] = InstructorReview.objects.filter(
            instructor=instructor
        ).count()
        
        # Set active menu attributes
        context['active_menu'] = 'content'
        context['active_submenu'] = 'instructors'
        
        # Set the layout path
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context


class InstructorReviewsView(DetailView):
    """View to display all reviews for an instructor"""
    model = Instructor
    context_object_name = 'instructor'
    template_name = 'instructor_reviews.html'
    slug_field = 'user__username'
    slug_url_kwarg = 'username'
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        instructor = self.get_object()
        
        # Get all reviews, with sorting options
        sort_option = self.request.GET.get('sort', 'newest')
        
        reviews = InstructorReview.objects.filter(instructor=instructor)
        
        if sort_option == 'oldest':
            reviews = reviews.order_by('created_at')
        elif sort_option == 'highest':
            reviews = reviews.order_by('-rating', '-created_at')
        elif sort_option == 'lowest':
            reviews = reviews.order_by('rating', '-created_at')
        else:  # Default: newest
            reviews = reviews.order_by('-created_at')
        
        context['reviews'] = reviews
        
        # Calculate rating stats
        from django.db.models import Count
        rating_counts = reviews.values('rating').annotate(count=Count('rating')).order_by('rating')
        
        # Convert to dictionaries for easier access in template
        context['rating_counts'] = {item['rating']: item['count'] for item in rating_counts}
        
        # Calculate percentages
        total_reviews = reviews.count()
        if total_reviews > 0:
            context['rating_percentages'] = {
                rating: (count / total_reviews) * 100 
                for rating, count in context['rating_counts'].items()
            }
        else:
            context['rating_percentages'] = {}
        
        # Calculate average rating
        if total_reviews > 0:
            context['average_rating'] = reviews.aggregate(Avg('rating'))['rating__avg']
        else:
            context['average_rating'] = 0
            
        # Calculate positive percentage (4-5 stars)
        positive_reviews = reviews.filter(rating__gte=4).count()
        if total_reviews > 0:
            context['positive_percentage'] = (positive_reviews / total_reviews) * 100
        else:
            context['positive_percentage'] = 0
        
        # Set active menu attributes
        context['active_menu'] = 'content'
        context['active_submenu'] = 'instructors'
        
        # Set the layout path
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context


class CreateInstructorProfileView(LoginRequiredMixin, CreateView):
    """View for users to create their instructor profile"""
    model = Instructor
    form_class = InstructorProfileForm
    template_name = 'instructor_profile_form.html'
    success_url = reverse_lazy('content:instructor_dashboard')
    
    # Removing the test_func for testing purposes
    
    def form_valid(self, form):
        # Check if user already has an instructor profile - commented out for testing
        # if hasattr(self.request.user, 'instructor_profile'):
        #     messages.warning(self.request, "You already have an instructor profile. Redirecting to update page.")
        #     return redirect('content:update_instructor_profile')
        
        # Set the user for this instructor profile
        form.instance.user = self.request.user
        
        messages.success(self.request, "Your instructor profile has been created successfully!")
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        context['title'] = 'Create Your Instructor Profile'
        context['submit_text'] = 'Save Profile'
        
        # Set active menu attributes
        context['active_menu'] = 'content'
        context['active_submenu'] = 'instructor_profile'
        
        # Set the layout path
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context


class UpdateInstructorProfileView(LoginRequiredMixin, UpdateView):
    """View for instructors to update their profile"""
    model = Instructor
    form_class = InstructorProfileForm
    template_name = 'instructor_profile_form.html'
    success_url = reverse_lazy('content:instructor_dashboard')
    
    def get_object(self, queryset=None):
        # Get the instructor profile for the current user
        # Create it if it doesn't exist
        instructor, created = Instructor.objects.get_or_create(user=self.request.user)
        return instructor
    
    def form_valid(self, form):
        messages.success(self.request, "Your instructor profile has been updated successfully!")
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        context['title'] = 'Update Your Instructor Profile'
        context['submit_text'] = 'Save Profile'
        
        # Set active menu attributes
        context['active_menu'] = 'content'
        context['active_submenu'] = 'instructor_profile'
        
        # Set the layout path
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context

class InstructorDashboardView(LoginRequiredMixin, TemplateView):
    """Dashboard for instructors to manage their sessions"""
    template_name = 'instructor_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))

        user = self.request.user

        # Check if the user has an instructor profile
        has_instructor_profile = hasattr(user, 'instructor_profile')
        context['has_instructor_profile'] = has_instructor_profile

        if has_instructor_profile:
            instructor = user.instructor_profile
            context['instructor'] = instructor

            # Current time
            now = timezone.now()

            # Get all private sessions/slots
            private_sessions = PrivateSession.objects.filter(
                instructor=instructor
            ).order_by('start_time')

            # Split into different categories
            context['upcoming_private_sessions'] = private_sessions.filter(
                start_time__gt=now,
                status__in=['available', 'booked']
            )

            context['private_slots'] = private_sessions.filter(
                status='available'
            )

            # Get all group sessions
            group_sessions = GroupSession.objects.filter(
                instructor=instructor
            ).order_by('start_time')

            context['upcoming_group_sessions'] = group_sessions.filter(
                start_time__gt=now,
                status='scheduled'
            )

            context['group_sessions'] = group_sessions.filter(
                status='scheduled'
            )

            # Get active sessions (currently happening)
            context['active_private_sessions'] = private_sessions.filter(
                start_time__lte=now,
                end_time__gte=now,
                status__in=['booked', 'active']
            )

            context['active_group_sessions'] = group_sessions.filter(
                start_time__lte=now,
                end_time__gte=now,
                status__in=['scheduled', 'active']
            )

            # Past sessions (combine private and group)
            past_private_sessions = private_sessions.filter(
                start_time__lt=now
            ).annotate(type=models.Value('private', output_field=models.CharField()))

            past_group_sessions = group_sessions.filter(
                start_time__lt=now
            ).annotate(type=models.Value('group', output_field=models.CharField()))

            # Combine and sort past sessions
            context['past_sessions'] = list(past_private_sessions) + list(past_group_sessions)
            context['past_sessions'].sort(key=lambda x: x.start_time, reverse=True)
            context['past_sessions'] = context['past_sessions'][:10]  # Limit to 10 most recent

            # Get recent reviews
            context['recent_reviews'] = InstructorReview.objects.filter(
                instructor=instructor
            ).order_by('-created_at')[:5]

            # Get courses taught by this instructor
            context['taught_courses'] = Course.objects.filter(
                teacher=user
            ).order_by('-created_at')

        # Set active menu attributes
        context['active_menu'] = 'instructor'
        context['active_submenu'] = 'instructor_dashboard'

        # Set the layout path
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)

        return context


class CreatePrivateSessionView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """View for creating private session slots"""
    model = PrivateSession
    form_class = PrivateSessionForm
    template_name = 'session_form.html'
    success_url = reverse_lazy('content:instructor_dashboard')
    
    def test_func(self):
        """Only users with instructor profiles can create sessions"""
        return hasattr(self.request.user, 'instructor_profile')
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        context['title'] = 'Create Private Session Slot'
        context['is_private'] = True
        context['is_update'] = False
        
        # Set active menu attributes
        context['active_menu'] = 'instructor'
        context['active_submenu'] = 'sessions'
        
        # Set the layout path
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context
    
    def form_valid(self, form):
        # Set the instructor to current user's profile
        instructor = self.request.user.instructor_profile

        # Save and get the instance
        instance = form.save(commit=False, instructor=instructor)

        # Set status based on action
        action = self.request.POST.get('action', 'publish')
        if action == 'publish':
            instance.status = 'available'
            instance.published_at = timezone.now()
            messages.success(self.request, "Private session slot published successfully!")
        else:
            instance.status = 'draft'
            messages.success(self.request, "Private session slot saved as draft!")

        instance.save()
    
        # Create corresponding entry in the booking app if available
        try:
            from apps.booking.models import PrivateSessionSlot, Instructor
            
            # Get or create instructor profile in booking app
            booking_instructor, created = Instructor.objects.get_or_create(
                user=self.request.user,
                defaults={
                    'bio': instructor.bio if hasattr(instructor, 'bio') else '',
                    'profile_image': instructor.profile_image if hasattr(instructor, 'profile_image') else None,
                    'teaching_languages': ','.join(instructor.teaching_languages.split(',')) if hasattr(instructor, 'teaching_languages') and instructor.teaching_languages else '',
                    'hourly_rate': instructor.hourly_rate if hasattr(instructor, 'hourly_rate') else 25.00
                }
            )

            # Create private session slot in booking app
            PrivateSessionSlot.objects.create(
                instructor=booking_instructor,
                start_time=instance.start_time,
                end_time=instance.end_time,
                duration_minutes=instance.duration_minutes,
                language=instance.language,
                level=instance.level,
                status='available' if instance.status == 'available' else 'draft'
            )
        except (ImportError, AttributeError) as e:
            # Booking app not available or models not compatible
            print(f"Error syncing with booking app: {e}")
            pass

        return HttpResponseRedirect(self.get_success_url())

class UpdatePrivateSessionView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """View for updating private session slots"""
    model = PrivateSession
    form_class = PrivateSessionForm
    template_name = 'session_form.html'
    pk_url_kwarg = 'session_id'
    success_url = reverse_lazy('content:instructor_dashboard')
    
    def test_func(self):
        """Only the session instructor can update sessions"""
        session = self.get_object()
        return hasattr(self.request.user, 'instructor_profile') and session.instructor == self.request.user.instructor_profile
    
    def get_initial(self):
        initial = super().get_initial()
        session = self.get_object()
        
        # Set initial date and time
        initial['session_date'] = session.start_time.date()
        initial['session_time'] = session.start_time.time()
        
        return initial
    
    def form_valid(self, form):
        # Get the existing session
        session = self.get_object()
        
        # Update the session with form data
        instance = form.save(commit=False)
        
        # Only allow updating if session is not booked
        if session.status in ['active', 'booked', 'completed', 'cancelled']:
            messages.error(self.request, "Cannot update a session that is already booked or completed.")
            return redirect(self.success_url)
        
        # Update and save
        instance.save()
        messages.success(self.request, "Private session updated successfully!")
        return redirect(self.success_url)
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        context['title'] = 'Update Private Session'
        context['is_private'] = True
        context['is_update'] = True
        
        # Set active menu attributes
        context['active_menu'] = 'instructor'
        context['active_submenu'] = 'sessions'
        
        # Set the layout path
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context


class DeletePrivateSessionView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """View for deleting private session slots"""
    model = PrivateSession
    template_name = 'session_confirm_delete.html'
    pk_url_kwarg = 'session_id'
    success_url = reverse_lazy('content:instructor_dashboard')
    
    def test_func(self):
        """Only the session instructor can delete sessions"""
        session = self.get_object()
        return hasattr(self.request.user, 'instructor_profile') and session.instructor == self.request.user.instructor_profile
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        context['title'] = 'Delete Private Session'
        context['is_private'] = True
        context['message'] = 'Are you sure you want to delete this private session slot?'
        context['back_url'] = self.success_url
        
        # Set active menu attributes
        context['active_menu'] = 'instructor'
        context['active_submenu'] = 'sessions'
        
        # Set the layout path
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context
    
    def delete(self, request, *args, **kwargs):
        session = self.get_object()
        
        # Don't allow deleting if the session is booked or completed
        if session.status in ['booked', 'active', 'completed']:
            messages.error(request, "Cannot delete a session that is already booked or completed.")
            return redirect(self.success_url)
        
        messages.success(request, "Private session deleted successfully.")
        return super().delete(request, *args, **kwargs)


class CreateGroupSessionView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """View for creating group sessions"""
    model = GroupSession
    form_class = GroupSessionForm
    template_name = 'session_form.html'
    success_url = reverse_lazy('content:instructor_dashboard')
    
    def test_func(self):
        """Only users with instructor profiles can create sessions"""
        return hasattr(self.request.user, 'instructor_profile')
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        context['title'] = 'Create Group Session'
        context['is_private'] = False
        context['is_update'] = False
        
        # Set active menu attributes
        context['active_menu'] = 'instructor'
        context['active_submenu'] = 'sessions'
        
        # Set the layout path
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context
    
    def form_valid(self, form):
        # Set the instructor to current user's profile
        instructor = self.request.user.instructor_profile

        # Save and get the instance
        instance = form.save(commit=False, instructor=instructor)

        # Set status based on action
        action = self.request.POST.get('action', 'publish')
        if action == 'publish':
            instance.status = 'scheduled'
            instance.published_at = timezone.now()
            messages.success(self.request, "Group session published successfully!")
        else:
            instance.status = 'draft'
            messages.success(self.request, "Group session saved as draft!")

        instance.save()

        # Create corresponding entry in the booking app if available
        try:
            from apps.booking.models import GroupSession as BookingGroupSession, Instructor
            
            # Get or create instructor profile in booking app
            booking_instructor, created = Instructor.objects.get_or_create(
                user=self.request.user,
                defaults={
                    'bio': instructor.bio if hasattr(instructor, 'bio') else '',
                    'profile_image': instructor.profile_image if hasattr(instructor, 'profile_image') else None,
                    'teaching_languages': ','.join(instructor.teaching_languages.split(',')) if hasattr(instructor, 'teaching_languages') and instructor.teaching_languages else '',
                    'hourly_rate': instructor.hourly_rate if hasattr(instructor, 'hourly_rate') else 25.00
                }
            )

            # Create group session in booking app
            BookingGroupSession.objects.create(
                title=instance.title,
                instructor=booking_instructor,
                language=instance.language,
                level=instance.level,
                description=instance.description,
                start_time=instance.start_time,
                end_time=instance.end_time,
                duration_minutes=instance.duration_minutes,
                max_students=instance.max_students,
                price=instance.price if hasattr(instance, 'price') else 15.00,
                status='scheduled'
            )
        except (ImportError, AttributeError) as e:
            # Booking app not available or models not compatible
            print(f"Error syncing with booking app: {e}")
            pass
        
        return HttpResponseRedirect(self.get_success_url())

class UpdateGroupSessionView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """View for updating group sessions"""
    model = GroupSession
    form_class = GroupSessionForm
    template_name = 'session_form.html'
    pk_url_kwarg = 'session_id'
    success_url = reverse_lazy('content:instructor_dashboard')
    
    def test_func(self):
        """Only the session instructor can update sessions"""
        session = self.get_object()
        return hasattr(self.request.user, 'instructor_profile') and session.instructor == self.request.user.instructor_profile
    
    def get_initial(self):
        initial = super().get_initial()
        session = self.get_object()
        
        # Set initial date and time
        initial['session_date'] = session.start_time.date()
        initial['session_time'] = session.start_time.time()
        
        return initial
    
    def form_valid(self, form):
        # Get the existing session
        session = self.get_object()
        
        # Update the session with form data
        instance = form.save(commit=False)
        
        # Don't allow reducing max_students below current enrollment
        if form.cleaned_data['max_students'] < session.students.count():
            messages.error(self.request, "Cannot set maximum students below current enrollment count.")
            return self.form_invalid(form)
        
        # Only allow updating if session has not started yet
        if session.start_time <= timezone.now():
            messages.error(self.request, "Cannot update a session that has already started.")
            return redirect(self.success_url)
        
        # Update and save
        instance.save()
        messages.success(self.request, "Group session updated successfully!")
        return redirect(self.success_url)
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        context['title'] = 'Update Group Session'
        context['is_private'] = False
        context['is_update'] = True
        
        # Set active menu attributes
        context['active_menu'] = 'instructor'
        context['active_submenu'] = 'sessions'
        
        # Set the layout path
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context


class DeleteGroupSessionView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """View for deleting group sessions"""
    model = GroupSession
    template_name = 'session_confirm_delete.html'
    pk_url_kwarg = 'session_id'
    success_url = reverse_lazy('content:instructor_dashboard')
    
    def test_func(self):
        """Only the session instructor can delete sessions"""
        session = self.get_object()
        return hasattr(self.request.user, 'instructor_profile') and session.instructor == self.request.user.instructor_profile
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        context['title'] = 'Delete Group Session'
        context['is_private'] = False
        context['message'] = 'Are you sure you want to delete this group session?'
        
        # Add warning if students are enrolled
        if self.object.students.exists():
            context['message'] += f' There are {self.object.students.count()} student{"s" if self.object.students.count() > 1 else ""} enrolled who will be notified of the cancellation.'
        
        context['back_url'] = self.success_url
        
        # Set active menu attributes
        context['active_menu'] = 'instructor'
        context['active_submenu'] = 'sessions'
        
        # Set the layout path
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context
    
    def delete(self, request, *args, **kwargs):
        session = self.get_object()
        
        # Notify enrolled students (would implement email notification here)
        if session.students.exists():
            # In a real implementation, send emails to students
            pass
        
        messages.success(request, "Group session deleted successfully.")
        return super().delete(request, *args, **kwargs)


class GroupSessionListView(ListView):
    """View to list all upcoming group sessions"""
    model = GroupSession
    context_object_name = 'group_sessions'
    template_name = 'group_session_list.html'
    paginate_by = 12
    
    def get_queryset(self):
        now = timezone.now()
        queryset = GroupSession.objects.filter(
            status='scheduled',
            start_time__gt=now
        ).select_related('instructor', 'instructor__user').order_by('start_time')
        
        # Filter by language
        language = self.request.GET.get('language')
        if language:
            queryset = queryset.filter(language=language)
        
        # Filter by level
        level = self.request.GET.get('level')
        if level:
            queryset = queryset.filter(level=level)
        
        # Filter by date
        date_filter = self.request.GET.get('date')
        if date_filter:
            try:
                filter_date = timezone.datetime.strptime(date_filter, '%Y-%m-%d').date()
                queryset = queryset.filter(start_time__date=filter_date)
            except ValueError:
                pass
        
        # Search by title or description
        search_query = self.request.GET.get('q')
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query) | 
                Q(description__icontains=search_query) |
                Q(tags__icontains=search_query)
            )
        
        # Mark sessions that user is enrolled in
        if self.request.user.is_authenticated:
            for session in queryset:
                session.is_enrolled = self.request.user in session.students.all()
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        # Add filter options
        context['language_choices'] = dict(Course.LANGUAGE_CHOICES)
        context['level_choices'] = dict(Course.LEVEL_CHOICES)
        
        # Current time for comparisons
        context['now'] = timezone.now()
        
        # Set active menu attributes
        context['active_menu'] = 'content'
        context['active_submenu'] = 'group_sessions'
        
        # Set the layout path
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context


class GroupSessionDetailView(DetailView):
    """View to display details of a group session"""
    model = GroupSession
    context_object_name = 'session'
    template_name = 'group_session_detail.html'
    pk_url_kwarg = 'session_id'
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        session = self.get_object()
        
        # Check if user is enrolled
        if self.request.user.is_authenticated:
            context['is_enrolled'] = self.request.user in session.students.all()
        
        # Get enrolled students
        context['enrolled_students'] = session.students.all()
        
        # Calculate available slots
        context['available_slots'] = session.max_students - session.students.count()
        
        # Current time for comparisons
        context['now'] = timezone.now()
        
        # Get related sessions (same language/level)
        context['related_sessions'] = GroupSession.objects.filter(
            status='scheduled',
            language=session.language,
            level=session.level,
            start_time__gt=timezone.now()
        ).exclude(id=session.id).order_by('start_time')[:3]
        
        # Set active menu attributes
        context['active_menu'] = 'content'
        context['active_submenu'] = 'group_sessions'
        
        # Set the layout path
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context
    
    def post(self, request, *args, **kwargs):
        """Handle enrollment/unenrollment"""
        session = self.get_object()
        action = request.POST.get('action')
        
        if not request.user.is_authenticated:
            messages.error(request, "Please log in to enroll in sessions.")
            return redirect('account:login')
        
        if action == 'enroll':
            # Check if session is full
            if session.is_full:
                messages.error(request, "This session is already full.")
                return redirect('content:group_session_detail', session_id=session.id)
            
            # Enroll student in session
            if request.user in session.students.all():
                messages.info(request, "You are already enrolled in this session.")
            else:
                session.students.add(request.user)
                messages.success(request, f"You have successfully enrolled in {session.title}.")
        
        elif action == 'unenroll':
            # Unenroll student from session
            if request.user in session.students.all():
                session.students.remove(request.user)
                messages.success(request, f"You have been unenrolled from {session.title}.")
            else:
                messages.info(request, "You are not enrolled in this session.")
        
        return redirect('content:group_session_detail', session_id=session.id)



class CreateInstructorReviewView(LoginRequiredMixin, CreateView):
    """View for students to leave reviews for instructors"""
    model = InstructorReview
    form_class = InstructorReviewForm
    template_name = 'review_form.html'
    
    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.instructor = get_object_or_404(Instructor, id=kwargs.get('instructor_id'))
        
        # Get session information if provided
        self.private_session = None
        self.group_session = None
        
        session_type = kwargs.get('session_type')
        session_id = kwargs.get('session_id')
        
        if session_type == 'private' and session_id:
            self.private_session = get_object_or_404(
                PrivateSession, 
                id=session_id,
                student=request.user,
                instructor=self.instructor
            )
        elif session_type == 'group' and session_id:
            self.group_session = get_object_or_404(
                GroupSession,
                id=session_id,
                students=request.user,
                instructor=self.instructor
            )
    
    def get_success_url(self):
        return reverse('content:instructor_detail', kwargs={'username': self.instructor.user.username})
    
    def form_valid(self, form):
        # Set the instructor and student
        form.instance.instructor = self.instructor
        form.instance.student = self.request.user
        
        messages.success(self.request, "Thank you for your review!")
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        context['instructor'] = self.instructor
        
        # Add session context if applicable
        if hasattr(self, 'private_session') and self.private_session:
            context['session'] = self.private_session
            context['session_type'] = 'private'
        elif hasattr(self, 'group_session') and self.group_session:
            context['session'] = self.group_session
            context['session_type'] = 'group'
        
        context['title'] = f'Review {self.instructor.user.username}'
        
        # Set active menu attributes
        context['active_menu'] = 'content'
        context['active_submenu'] = 'instructors'
        
        # Set the layout path
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context


class StudentDashboardView(LoginRequiredMixin, TemplateView):
    """Dashboard for students to view their enrolled courses and sessions"""
    template_name = 'student_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        user = self.request.user
        now = timezone.now()
        
        # Get enrolled courses
        context['enrolled_courses'] = user.enrolled_courses.all().order_by('-courseProgress__last_accessed')
        
        # Get progress for each course
        course_progress = {}
        for course in context['enrolled_courses']:
            progress, created = CourseProgress.objects.get_or_create(
                student=user,
                course=course
            )
            course_progress[course.id] = progress.progress_percentage
        
        context['course_progress'] = course_progress
        
        # Get upcoming private sessions
        context['upcoming_private_sessions'] = PrivateSession.objects.filter(
            student=user,
            status='booked',
            start_time__gt=now
        ).select_related('instructor', 'instructor__user').order_by('start_time')
        
        # Get past private sessions
        context['past_private_sessions'] = PrivateSession.objects.filter(
            student=user,
            start_time__lt=now
        ).select_related('instructor', 'instructor__user').order_by('-start_time')[:10]
        
        # Get enrolled group sessions
        context['upcoming_group_sessions'] = GroupSession.objects.filter(
            students=user,
            status='scheduled',
            start_time__gt=now
        ).select_related('instructor', 'instructor__user').order_by('start_time')
        
        # Get past group sessions
        context['past_group_sessions'] = GroupSession.objects.filter(
            students=user,
            start_time__lt=now
        ).select_related('instructor', 'instructor__user').order_by('-start_time')[:10]
        
        # Get recently completed lessons
        context['recent_lessons'] = LessonCompletion.objects.filter(
            student=user
        ).select_related('lesson', 'lesson__module', 'lesson__module__course').order_by('-completed_at')[:5]
        
        # Set active menu attributes
        context['active_menu'] = 'student'
        context['active_submenu'] = 'dashboard'
        
        # Set the layout path
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context


class CreateSessionFeedbackView(LoginRequiredMixin, CreateView):
    """View for students to provide feedback after sessions"""
    model = SessionFeedback
    form_class = SessionFeedbackForm
    template_name = 'feedback_form.html'
    
    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        
        session_type = kwargs.get('session_type')
        session_id = kwargs.get('session_id')
        
        self.private_session = None
        self.group_session = None
        
        if session_type == 'private':
            self.private_session = get_object_or_404(
                PrivateSession, 
                id=session_id,
                student=request.user
            )
            self.instructor = self.private_session.instructor
        elif session_type == 'group':
            self.group_session = get_object_or_404(
                GroupSession,
                id=session_id
            )
            # Verify the user is enrolled
            if not self.group_session.students.filter(id=request.user.id).exists():
                raise Http404("You are not enrolled in this session")
            self.instructor = self.group_session.instructor
    
    def get_success_url(self):
        return reverse('content:student_dashboard')
    
    def form_valid(self, form):
        # Set the session information
        form.instance.user = self.request.user
        
        if hasattr(self, 'private_session') and self.private_session:
            form.instance.session_type = 'private'
            form.instance.private_session = self.private_session
        elif hasattr(self, 'group_session') and self.group_session:
            form.instance.session_type = 'group'
            form.instance.group_session = self.group_session
        
        messages.success(self.request, "Thank you for your feedback!")
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        # Add session info to context
        if hasattr(self, 'private_session') and self.private_session:
            context['session'] = self.private_session
            context['session_type'] = 'private'
        elif hasattr(self, 'group_session') and self.group_session:
            context['session'] = self.group_session
            context['session_type'] = 'group'
        
        context['instructor'] = self.instructor
        context['title'] = 'Session Feedback'
        
        # Set active menu attributes
        context['active_menu'] = 'student'
        context['active_submenu'] = 'dashboard'
        
        # Set the layout path
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context


class SessionFeedbackListView(LoginRequiredMixin, ListView):
    """View for instructors to view feedback for their sessions"""
    model = SessionFeedback
    context_object_name = 'feedbacks'
    template_name = 'feedback_list.html'
    paginate_by = 10
    
    def get_queryset(self):
        # Only instructors can see their feedback
        if not hasattr(self.request.user, 'instructor_profile'):
            return SessionFeedback.objects.none()
        
        instructor = self.request.user.instructor_profile
        
        # Get feedback for both session types
        queryset = SessionFeedback.objects.filter(
            Q(private_session__instructor=instructor) |
            Q(group_session__instructor=instructor)
        ).select_related('user', 'private_session', 'group_session').order_by('-created_at')
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        # Calculate average ratings
        queryset = self.get_queryset()
        
        if queryset.exists():
            avg_rating = queryset.aggregate(Avg('rating'))['rating__avg']
            context['average_rating'] = avg_rating
            
            # Calculate rating distribution
            from django.db.models import Count
            ratings = queryset.values('rating').annotate(count=Count('rating')).order_by('rating')
            
            total = queryset.count()
            rating_counts = {r['rating']: r['count'] for r in ratings}
            rating_percentages = {r: (c/total)*100 for r, c in rating_counts.items()}
            
            context['rating_counts'] = rating_counts
            context['rating_percentages'] = rating_percentages
        
        context['title'] = 'Session Feedback'
        
        # Set active menu attributes
        context['active_menu'] = 'instructor'
        context['active_submenu'] = 'feedback'
        
        # Set the layout path
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context


# URL mapping helper functions

def get_course_lessons(request, course_id):
    """API endpoint to get lessons for a specific course"""
    course = get_object_or_404(Course, id=course_id)
    
    # Check permissions
    if not request.user.is_superuser:
        if request.user != course.teacher and request.user not in course.students.all():
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


def session_preview_data(request):
    """Returns session preview data as JSON"""
    if request.method == 'POST':
        is_private = request.POST.get('is_private') == 'true'
        
        # Get session details from POST
        language_code = request.POST.get('language')
        level_code = request.POST.get('level')
        session_date = request.POST.get('session_date')
        session_time = request.POST.get('session_time')
        duration_minutes = request.POST.get('duration_minutes')
        
        # Format data for preview
        data = {
            'session_type': 'Private 1-on-1' if is_private else 'Group',
            'language': dict(Course.LANGUAGE_CHOICES).get(language_code, ''),
            'level': dict(Course.LEVEL_CHOICES).get(level_code, ''),
            'datetime': '',
            'duration': '',
            'status': 'Draft'
        }
        
        # Format date/time if provided
        if session_date and session_time:
            try:
                import datetime
                date_obj = datetime.datetime.strptime(session_date, '%Y-%m-%d').date()
                time_obj = datetime.datetime.strptime(session_time, '%H:%M').time()
                session_datetime = datetime.datetime.combine(date_obj, time_obj)
                data['datetime'] = session_datetime.strftime('%b %d, %Y at %H:%M')
            except (ValueError, TypeError):
                pass
        
        # Format duration if provided
        if duration_minutes:
            try:
                mins = int(duration_minutes)
                if mins == 60:
                    data['duration'] = '1 hour'
                elif mins == 90:
                    data['duration'] = '1.5 hours'
                elif mins == 120:
                    data['duration'] = '2 hours'
                else:
                    data['duration'] = f'{mins} minutes'
            except (ValueError, TypeError):
                pass
        
        return JsonResponse(data)
    
    return JsonResponse({'error': 'Only POST requests are supported'}, status=400)        