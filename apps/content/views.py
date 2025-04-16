from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View
from django.views.generic.edit import FormMixin
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy, reverse
from django.http import JsonResponse, HttpResponseRedirect
from django.contrib import messages
from django.utils.text import slugify
from django.db.models import Count, Q
from web_project import TemplateLayout
from web_project.template_helpers.theme import TemplateHelper

from .models import (
    Course, LearningModule, Lesson, Resource, Language, 
    LanguageLevel, CourseProgress, LessonCompletion
)
from .forms import (
    CourseForm, ModuleForm, LessonForm, ResourceForm,
    CourseFilterForm, ResourceFilterForm
)

from .api import get_course_lessons, mark_lesson_complete

from django.contrib.auth.models import User


class LanguageCoursesView(ListView):
    """View to list courses by language"""
    model = Course
    context_object_name = 'courses'
    template_name = 'language_courses.html'
    paginate_by = 12
    
    def get_queryset(self):
        language_code = self.kwargs.get('language_code')
        if language_code:
            return Course.objects.filter(
                language__code=language_code,
                is_published=True
            ).select_related('language', 'level', 'teacher')
        return Course.objects.filter(is_published=True).select_related('language', 'level', 'teacher')
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        language_code = self.kwargs.get('language_code')
        if language_code:
            context['current_language'] = get_object_or_404(Language, code=language_code)
        
        context['languages'] = Language.objects.filter(is_active=True)
        context['levels'] = LanguageLevel.objects.all()
        context['filter_form'] = CourseFilterForm(self.request.GET)
        
        # Set active menu attributes
        context['active_menu'] = 'content'
        context['active_submenu'] = 'courses'
        
        # Set the layout path using TemplateHelper
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context


class CourseListView(ListView):
    """View to list all courses with filtering options"""
    model = Course
    context_object_name = 'courses'
    template_name = 'course_list.html'
    paginate_by = 12
    
    def get_queryset(self):
        queryset = Course.objects.filter(is_published=True).select_related(
            'language', 'level', 'teacher'
        )
        
        # Filter by language
        language_id = self.request.GET.get('language')
        if language_id:
            queryset = queryset.filter(language_id=language_id)
        
        # Filter by level
        level_id = self.request.GET.get('level')
        if level_id:
            queryset = queryset.filter(level_id=level_id)
        
        # Search by title or description
        search_query = self.request.GET.get('q')
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query) | 
                Q(description__icontains=search_query)
            )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        context['languages'] = Language.objects.filter(is_active=True)
        context['levels'] = LanguageLevel.objects.all()
        context['filter_form'] = CourseFilterForm(self.request.GET)
        
        # Get featured courses for the sidebar
        context['featured_courses'] = Course.objects.filter(
            is_featured=True, 
            is_published=True
        ).select_related('language', 'level').order_by('?')[:5]
        
        # Set active menu attributes
        context['active_menu'] = 'content'
        context['active_submenu'] = 'courses'
        
        # Set the layout path using TemplateHelper
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context


class TeacherCourseListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """View for teachers to see courses they teach"""
    model = Course
    context_object_name = 'courses'
    template_name = 'teacher_courses.html'
    
    def test_func(self):
        return self.request.user.is_teacher or self.request.user.is_superuser
    
    def get_queryset(self):
        return Course.objects.filter(teacher=self.request.user).select_related(
            'language', 'level'
        ).prefetch_related('students')
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        context['published_count'] = self.get_queryset().filter(is_published=True).count()
        context['draft_count'] = self.get_queryset().filter(is_published=False).count()
        context['total_students'] = User.objects.filter(
            enrolled_courses__teacher=self.request.user
        ).distinct().count()
        
        # Set active menu attributes
        context['active_menu'] = 'content'
        context['active_submenu'] = 'my_courses'
        
        # Set the layout path using TemplateHelper
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context


class StudentCourseListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """View for students to see courses they're enrolled in"""
    model = Course
    context_object_name = 'courses'
    template_name = 'student_courses.html'
    
    def test_func(self):
        return self.request.user.is_student or self.request.user.is_superuser
    
    def get_queryset(self):
        return self.request.user.enrolled_courses.all().select_related(
            'language', 'level', 'teacher'
        )
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        # Calculate progress for each course
        courses_with_progress = []
        for course in context['courses']:
            try:
                progress = CourseProgress.objects.get(
                    student=self.request.user,
                    course=course
                )
                course.progress_percentage = progress.progress_percentage
                course.last_accessed = progress.last_accessed
            except CourseProgress.DoesNotExist:
                course.progress_percentage = 0
                course.last_accessed = None
            
            courses_with_progress.append(course)
        
        context['courses'] = courses_with_progress
        
        # Recommended courses
        enrolled_courses = self.request.user.enrolled_courses.all()
        context['recommended_courses'] = Course.objects.filter(
            is_published=True
        ).exclude(
            id__in=enrolled_courses.values_list('id', flat=True)
        ).select_related(
            'language', 'level', 'teacher'
        ).order_by('?')[:3]
        
        # Set active menu attributes
        context['active_menu'] = 'content'
        context['active_submenu'] = 'enrolled_courses'
        
        # Set the layout path using TemplateHelper
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context


class CourseDetailView(DetailView):
    """View to display course details"""
    model = Course
    context_object_name = 'course'
    template_name = 'course_detail.html'
    slug_url_kwarg = 'slug'
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        course = self.get_object()
        
        # Check if user is enrolled
        if self.request.user.is_authenticated:
            context['is_enrolled'] = course.students.filter(id=self.request.user.id).exists()
            
            # Get progress if enrolled
            if context['is_enrolled']:
                try:
                    progress = CourseProgress.objects.get(
                        student=self.request.user,
                        course=course
                    )
                    context['progress_percentage'] = progress.progress_percentage
                    
                    # Get lessons completed
                    context['completed_lessons'] = progress.lessons_completed.values_list('id', flat=True)
                except CourseProgress.DoesNotExist:
                    context['progress_percentage'] = 0
                    context['completed_lessons'] = []
        
        # Get modules and lessons
        context['modules'] = LearningModule.objects.filter(
            course=course
        ).prefetch_related('lessons').order_by('order')
        
        # Get teacher's other courses
        context['teacher_other_courses'] = Course.objects.filter(
            teacher=course.teacher,
            is_published=True
        ).exclude(id=course.id).order_by('?')[:3]
        
        # Get similar courses (same language, different levels)
        context['similar_courses'] = Course.objects.filter(
            language=course.language,
            is_published=True
        ).exclude(id=course.id).order_by('?')[:3]
        
        # Set active menu attributes
        context['active_menu'] = 'content'
        context['active_submenu'] = 'courses'
        
        # Set the layout path using TemplateHelper
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context


class CourseEnrollView(LoginRequiredMixin, UserPassesTestMixin, View):
    """View to handle course enrollment"""
    
    def test_func(self):
        return self.request.user.is_student or self.request.user.is_superuser
    
    def post(self, request, *args, **kwargs):
        course = get_object_or_404(Course, slug=kwargs.get('slug'))
        
        # Check if already enrolled
        if course.students.filter(id=request.user.id).exists():
            messages.info(request, "You are already enrolled in this course.")
            return redirect('content:course_detail', slug=course.slug)
        
        # Enroll the student
        course.add_student(request.user)
        
        # Create a progress record
        CourseProgress.objects.create(
            student=request.user,
            course=course
        )
        
        messages.success(request, f"You have successfully enrolled in {course.title}!")
        return redirect('content:course_detail', slug=course.slug)


class CourseUnenrollView(LoginRequiredMixin, UserPassesTestMixin, View):
    """View to handle course unenrollment"""
    
    def test_func(self):
        return self.request.user.is_student or self.request.user.is_superuser
    
    def post(self, request, *args, **kwargs):
        course = get_object_or_404(Course, slug=kwargs.get('slug'))
        
        # Check if enrolled
        if not course.students.filter(id=request.user.id).exists():
            messages.error(request, "You are not enrolled in this course.")
            return redirect('content:course_detail', slug=course.slug)
        
        # Unenroll the student
        course.remove_student(request.user)
        
        # Delete progress record
        CourseProgress.objects.filter(
            student=request.user,
            course=course
        ).delete()
        
        messages.success(request, f"You have been unenrolled from {course.title}.")
        return redirect('content:course_list')


class CourseCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """View to create a new course"""
    model = Course
    form_class = CourseForm
    template_name = 'course_form.html'
    
    def test_func(self):
        return self.request.user.is_teacher or self.request.user.is_superuser
    
    def form_valid(self, form):
        form.instance.teacher = self.request.user
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        context['title'] = 'Create New Course'
        context['submit_text'] = 'Create Course'
        
        # Set active menu attributes
        context['active_menu'] = 'content'
        context['active_submenu'] = 'my_courses'
        
        # Set the layout path using TemplateHelper
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context


class CourseUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """View to update an existing course"""
    model = Course
    form_class = CourseForm
    template_name = 'course_form.html'
    slug_url_kwarg = 'slug'
    
    def test_func(self):
        course = self.get_object()
        return self.request.user == course.teacher or self.request.user.is_superuser
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        context['title'] = 'Edit Course'
        context['submit_text'] = 'Update Course'
        
        # Set active menu attributes
        context['active_menu'] = 'content'
        context['active_submenu'] = 'my_courses'
        
        # Set the layout path using TemplateHelper
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context


class CourseDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """View to delete a course"""
    model = Course
    template_name = 'course_confirm_delete.html'
    success_url = reverse_lazy('content:teacher_courses')
    slug_url_kwarg = 'slug'
    
    def test_func(self):
        course = self.get_object()
        return self.request.user == course.teacher or self.request.user.is_superuser
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        # Set active menu attributes
        context['active_menu'] = 'content'
        context['active_submenu'] = 'my_courses'
        
        # Set the layout path using TemplateHelper
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context


class ModuleCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """View to create a new module in a course"""
    model = LearningModule
    form_class = ModuleForm
    template_name = 'module_form.html'
    
    def test_func(self):
        course = get_object_or_404(Course, slug=self.kwargs.get('course_slug'))
        return self.request.user == course.teacher or self.request.user.is_superuser
    
    def form_valid(self, form):
        course = get_object_or_404(Course, slug=self.kwargs.get('course_slug'))
        form.instance.course = course
        form.instance.order = LearningModule.objects.filter(course=course).count() + 1
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        course = get_object_or_404(Course, slug=self.kwargs.get('course_slug'))
        context['course'] = course
        context['title'] = f'Add Module to {course.title}'
        context['submit_text'] = 'Create Module'
        
        # Set active menu attributes
        context['active_menu'] = 'content'
        context['active_submenu'] = 'my_courses'
        
        # Set the layout path using TemplateHelper
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context
    
    def get_success_url(self):
        return reverse('content:course_detail', kwargs={'slug': self.kwargs.get('course_slug')})


class ModuleUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """View to update a module"""
    model = LearningModule
    form_class = ModuleForm
    template_name = 'module_form.html'
    pk_url_kwarg = 'module_id'
    
    def test_func(self):
        module = self.get_object()
        return self.request.user == module.course.teacher or self.request.user.is_superuser
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        module = self.get_object()
        context['course'] = module.course
        context['title'] = f'Edit Module: {module.title}'
        context['submit_text'] = 'Update Module'
        
        # Set active menu attributes
        context['active_menu'] = 'content'
        context['active_submenu'] = 'my_courses'
        
        # Set the layout path using TemplateHelper
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context
    
    def get_success_url(self):
        module = self.get_object()
        return reverse('content:course_detail', kwargs={'slug': module.course.slug})


class ModuleDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """View to delete a module"""
    model = LearningModule
    template_name = 'module_confirm_delete.html'
    pk_url_kwarg = 'module_id'
    
    def test_func(self):
        module = self.get_object()
        return self.request.user == module.course.teacher or self.request.user.is_superuser
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        # Set active menu attributes
        context['active_menu'] = 'content'
        context['active_submenu'] = 'my_courses'
        
        # Set the layout path using TemplateHelper
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context
    
    def get_success_url(self):
        module = self.get_object()
        return reverse('content:course_detail', kwargs={'slug': module.course.slug})


class LessonListView(LoginRequiredMixin, ListView):
    """View to list all lessons"""
    model = Lesson
    context_object_name = 'lessons'
    template_name = 'lesson_list.html'
    paginate_by = 12
    
    def get_queryset(self):
        if self.request.user.is_teacher:
            # Teachers see lessons from courses they teach
            return Lesson.objects.filter(
                module__course__teacher=self.request.user
            ).select_related('module', 'module__course')
        else:
            # Students see lessons from courses they're enrolled in
            return Lesson.objects.filter(
                module__course__students=self.request.user
            ).select_related('module', 'module__course')
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        # Set active menu attributes
        context['active_menu'] = 'content'
        context['active_submenu'] = 'content-lessons'
        
        # Set the layout path using TemplateHelper
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context

class LessonCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """View to create a new lesson in a module"""
    model = Lesson
    form_class = LessonForm
    template_name = 'lesson_form.html'
    
    def test_func(self):
        module = get_object_or_404(LearningModule, id=self.kwargs.get('module_id'))
        return self.request.user == module.course.teacher or self.request.user.is_superuser
    
    def form_valid(self, form):
        module = get_object_or_404(LearningModule, id=self.kwargs.get('module_id'))
        form.instance.module = module
        form.instance.order = Lesson.objects.filter(module=module).count() + 1
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        module = get_object_or_404(LearningModule, id=self.kwargs.get('module_id'))
        context['module'] = module
        context['course'] = module.course
        context['title'] = f'Add Lesson to {module.title}'
        context['submit_text'] = 'Create Lesson'
        
        # Set active menu attributes
        context['active_menu'] = 'content'
        context['active_submenu'] = 'my_courses'
        
        # Set the layout path using TemplateHelper
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context
    
    def get_success_url(self):
        module = get_object_or_404(LearningModule, id=self.kwargs.get('module_id'))
        return reverse('content:course_detail', kwargs={'slug': module.course.slug})


class LessonUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """View to update a lesson"""
    model = Lesson
    form_class = LessonForm
    template_name = 'lesson_form.html'
    slug_url_kwarg = 'lesson_slug'
    
    def test_func(self):
        lesson = self.get_object()
        return self.request.user == lesson.module.course.teacher or self.request.user.is_superuser
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        lesson = self.get_object()
        context['module'] = lesson.module
        context['course'] = lesson.module.course
        context['title'] = f'Edit Lesson: {lesson.title}'
        context['submit_text'] = 'Update Lesson'
        
        # Set active menu attributes
        context['active_menu'] = 'content'
        context['active_submenu'] = 'my_courses'
        
        # Set the layout path using TemplateHelper
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context
    
    def get_success_url(self):
        lesson = self.get_object()
        return reverse('content:course_detail', kwargs={'slug': lesson.module.course.slug})


class LessonDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """View to delete a lesson"""
    model = Lesson
    template_name = 'lesson_confirm_delete.html'
    slug_url_kwarg = 'lesson_slug'
    
    def test_func(self):
        lesson = self.get_object()
        return self.request.user == lesson.module.course.teacher or self.request.user.is_superuser
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        # Set active menu attributes
        context['active_menu'] = 'content'
        context['active_submenu'] = 'my_courses'
        
        # Set the layout path using TemplateHelper
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context
    
    def get_success_url(self):
        lesson = self.get_object()
        return reverse('content:course_detail', kwargs={'slug': lesson.module.course.slug})


class LessonDetailView(LoginRequiredMixin, DetailView):
    """View to display lesson content"""
    model = Lesson
    context_object_name = 'lesson'
    template_name = 'lesson_detail.html'
    slug_url_kwarg = 'lesson_slug'
    
    def get_object(self):
        course_slug = self.kwargs.get('course_slug')
        lesson_slug = self.kwargs.get('lesson_slug')
        
        return get_object_or_404(
            Lesson, 
            slug=lesson_slug,
            module__course__slug=course_slug
        )
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        lesson = self.get_object()
        course = lesson.module.course
        
        # Check if user is enrolled
        if not course.students.filter(id=self.request.user.id).exists() and not self.request.user == course.teacher:
            return redirect('content:course_detail', slug=course.slug)
        
        context['course'] = course
        context['module'] = lesson.module
        
        # Get next and previous lessons
        lessons_in_module = Lesson.objects.filter(module=lesson.module).order_by('order')
        
        lesson_index = None
        for i, l in enumerate(lessons_in_module):
            if l.id == lesson.id:
                lesson_index = i
                break
        
        if lesson_index is not None:
            if lesson_index > 0:
                context['prev_lesson'] = lessons_in_module[lesson_index - 1]
            
            if lesson_index < len(lessons_in_module) - 1:
                context['next_lesson'] = lessons_in_module[lesson_index + 1]
        
        # Get all modules for navigation
        context['modules'] = LearningModule.objects.filter(course=course).order_by('order')
        
        # Mark lesson as completed for student
        if self.request.user.is_student and course.students.filter(id=self.request.user.id).exists():
            try:
                # Get or create course progress
                progress, created = CourseProgress.objects.get_or_create(
                    student=self.request.user,
                    course=course
                )
                
                # Mark lesson as completed
                LessonCompletion.objects.get_or_create(
                    student=self.request.user,
                    lesson=lesson
                )
                
            except Exception as e:
                # Handle any errors in marking completion
                pass
        
        # Get related resources for this lesson
        context['resources'] = Resource.objects.filter(lesson=lesson)
        
        # Check if lesson is completed by the current student
        if self.request.user.is_student:
            context['is_completed'] = LessonCompletion.objects.filter(
                student=self.request.user,
                lesson=lesson
            ).exists()
        
        # Set active menu attributes
        context['active_menu'] = 'content'
        context['active_submenu'] = 'courses'
        
        # Set the layout path using TemplateHelper
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context

    def post(self, request, *args, **kwargs):
        """Handle marking lesson as completed via POST request"""
        lesson = self.get_object()
        course = lesson.module.course
        
        # Check if user is enrolled and is a student
        if request.user.is_student and course.students.filter(id=request.user.id).exists():
            # Mark lesson as completed
            try:
                # Get or create course progress
                progress, created = CourseProgress.objects.get_or_create(
                    student=request.user,
                    course=course
                )
                
                # Mark lesson as completed
                completion, created = LessonCompletion.objects.get_or_create(
                    student=request.user,
                    lesson=lesson
                )
                
                if created:
                    return JsonResponse({'status': 'success', 'message': 'Lesson marked as completed'})
                else:
                    return JsonResponse({'status': 'info', 'message': 'Lesson was already completed'})
                
            except Exception as e:
                return JsonResponse({'status': 'error', 'message': str(e)})
        
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)


class ResourceListView(LoginRequiredMixin, ListView):
    """View to list learning resources"""
    model = Resource
    context_object_name = 'resources'
    template_name = 'resource_list.html'
    paginate_by = 12
    
    def get_queryset(self):
        queryset = Resource.objects.all()
        
        # Students only see public resources and those shared with them
        if self.request.user.is_student:
            queryset = queryset.filter(
                is_public=True
            )
        # Teachers see their own resources
        elif self.request.user.is_teacher:
            queryset = queryset.filter(created_by=self.request.user)
        # Admin sees all
        
        # Apply filters from form
        form = ResourceFilterForm(self.request.GET)
        if form.is_valid():
            language = form.cleaned_data.get('language')
            level = form.cleaned_data.get('level')
            resource_type = form.cleaned_data.get('resource_type')
            search_query = form.cleaned_data.get('q')
            
            if language:
                queryset = queryset.filter(language=language)
            if level:
                queryset = queryset.filter(level=level)
            if resource_type:
                queryset = queryset.filter(resource_type=resource_type)
            if search_query:
                queryset = queryset.filter(
                    Q(title__icontains=search_query) | 
                    Q(description__icontains=search_query)
                )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        context['filter_form'] = ResourceFilterForm(self.request.GET)
        
        # Get languages and levels for filters
        context['languages'] = Language.objects.filter(is_active=True)
        context['levels'] = LanguageLevel.objects.all()
        context['resource_types'] = Resource.RESOURCE_TYPES
        
        # Set active menu attributes
        context['active_menu'] = 'content'
        context['active_submenu'] = 'resources'
        
        # Set the layout path using TemplateHelper
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context


class ResourceCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """View to create a new learning resource"""
    model = Resource
    form_class = ResourceForm
    template_name = 'resource_form.html'
    
    def test_func(self):
        """Only teachers can create resources"""
        return self.request.user.is_teacher or self.request.user.is_superuser
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('content:resource_list')
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        context['title'] = 'Create New Resource'
        context['submit_text'] = 'Create Resource'
        
        # Set active menu attributes
        context['active_menu'] = 'content'
        context['active_submenu'] = 'resources'
        
        # Set the layout path using TemplateHelper
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context


class ResourceUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """View to update an existing learning resource"""
    model = Resource
    form_class = ResourceForm
    template_name = 'resource_form.html'
    pk_url_kwarg = 'resource_id'
    
    def test_func(self):
        """Only the creator or admin can edit resources"""
        resource = self.get_object()
        return self.request.user == resource.created_by or self.request.user.is_superuser
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def get_success_url(self):
        return reverse('content:resource_list')
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        context['title'] = 'Edit Resource'
        context['submit_text'] = 'Update Resource'
        
        # Set active menu attributes
        context['active_menu'] = 'content'
        context['active_submenu'] = 'resources'
        
        # Set the layout path using TemplateHelper
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context


class ResourceDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """View to delete a resource"""
    model = Resource
    template_name = 'resource_confirm_delete.html'
    pk_url_kwarg = 'resource_id'
    success_url = reverse_lazy('content:resource_list')
    
    def test_func(self):
        """Only the creator or admin can delete resources"""
        resource = self.get_object()
        return self.request.user == resource.created_by or self.request.user.is_superuser
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        # Set active menu attributes
        context['active_menu'] = 'content'
        context['active_submenu'] = 'resources'
        
        # Set the layout path using TemplateHelper
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context
    
    def get(self, request, *args, **kwargs):
        """Skip confirmation page and redirect to POST handling"""
        return self.post(request, *args, **kwargs)