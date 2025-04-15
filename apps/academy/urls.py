from django.urls import path
from .views import (
    AcademyDashboardView,
    AcademyCoursesView, 
    AcademyMyCoursesView,
    AcademyCourseDetailView,
    AcademyLessonPlanningView,
    AcademyResourcesView,
    AcademyAssessmentsView,
    AcademyRepositoryView
)

urlpatterns = [
    # Dashboard view
    path(
        "app/academy/dashboard/", 
        AcademyDashboardView.as_view(), 
        name="app-academy-dashboard"
    ),
    
    # All Courses view
    path(
        "app/academy/courses/", 
        AcademyCoursesView.as_view(), 
        name="app-academy-courses"
    ),
    
    # My Courses view
    path(
        "app/academy/my-courses/", 
        AcademyMyCoursesView.as_view(), 
        name="app-academy-my-courses"
    ),
    
    # Course details view
    path(
        "app/academy/course/<int:course_id>/", 
        AcademyCourseDetailView.as_view(), 
        name="app-academy-course-details"
    ),
    
    # Lesson planning view
    path(
        "app/academy/lessons/", 
        AcademyLessonPlanningView.as_view(), 
        name="app-academy-lessons"
    ),
    
    # Resources view
    path(
        "app/academy/resources/", 
        AcademyResourcesView.as_view(), 
        name="app-academy-resources"
    ),
    
    # Assessments view
    path(
        "app/academy/assessments/", 
        AcademyAssessmentsView.as_view(), 
        name="app-academy-assessments"
    ),
    
    # Repository view
    path(
        "app/academy/repository/", 
        AcademyRepositoryView.as_view(), 
        name="app-academy-repository"
    ),
]