from django.views.generic import TemplateView, ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from web_project import TemplateLayout
from .models import Course, Lesson, UserProgress, Resource, Assessment

"""
This file is a view controller for multiple pages as a module.
Here you can override the page view layout.
Refer to academy/urls.py file for more pages.
"""

class AcademyBaseView(LoginRequiredMixin, TemplateView):
    """Base view for Academy pages, containing common methods"""
    
    def get_context_data(self, **kwargs):
        # A function to init the global layout
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        return context


class AcademyDashboardView(AcademyBaseView):
    """Dashboard view for the Academy app"""
    template_name = "app_academy_dashboard.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add data needed for the dashboard
        return context


class AcademyCoursesView(AcademyBaseView):
    """View for displaying all available courses"""
    template_name = "app_academy_courses.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get all courses
        return context


class AcademyMyCoursesView(AcademyBaseView):
    """View for displaying user's enrolled courses"""
    template_name = "app_academy_course.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get user's enrolled courses
        return context


class AcademyCourseDetailView(AcademyBaseView):
    """View for displaying course details"""
    template_name = "app_academy_course_details.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        course_id = kwargs.get('course_id')
        if course_id:
            # Get course details
            pass
        return context


class AcademyLessonPlanningView(AcademyBaseView):
    """View for lesson planning functionality (for instructors)"""
    template_name = "app_academy_lessons.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get lesson planning data
        return context


class AcademyResourcesView(AcademyBaseView):
    """View for resources section"""
    template_name = "app_academy_resources.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get resources
        return context


class AcademyAssessmentsView(AcademyBaseView):
    """View for assessments section"""
    template_name = "app_academy_assessments.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Logic for assessments view
        return context


class AcademyRepositoryView(AcademyBaseView):
    """View for file repository section"""
    template_name = "app_academy_repository.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Logic for repository view
        return context