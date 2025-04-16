from django.urls import path
from . import views

app_name = 'content'

urlpatterns = [
    # API endpoints
    path('api/courses/<int:course_id>/lessons/', views.get_course_lessons, name='api_course_lessons'),
    path('api/lessons/<int:lesson_id>/complete/', views.mark_lesson_complete, name='mark_lesson_complete'),
    
    # Course views
    path('courses/', views.CourseListView.as_view(), name='course_list'),
    path('courses/create/', views.CourseCreateView.as_view(), name='create_course'),
    path('courses/<slug:slug>/', views.CourseDetailView.as_view(), name='course_detail'),
    path('courses/<slug:slug>/edit/', views.CourseUpdateView.as_view(), name='edit_course'),
    path('courses/<slug:slug>/delete/', views.CourseDeleteView.as_view(), name='delete_course'),
    path('courses/<slug:slug>/enroll/', views.CourseEnrollView.as_view(), name='enroll_course'),
    path('courses/<slug:slug>/unenroll/', views.CourseUnenrollView.as_view(), name='unenroll_course'),
    
    # Teacher & Student specific course views
    path('my-courses/teaching/', views.TeacherCourseListView.as_view(), name='teacher_courses'),
    path('my-courses/learning/', views.StudentCourseListView.as_view(), name='student_courses'),
    
    # Modules
    path('courses/<slug:course_slug>/modules/create/', views.ModuleCreateView.as_view(), name='create_module'),
    path('modules/<int:module_id>/edit/', views.ModuleUpdateView.as_view(), name='edit_module'),
    path('modules/<int:module_id>/delete/', views.ModuleDeleteView.as_view(), name='delete_module'),
    
    # Lessons
    path('modules/<int:module_id>/lessons/create/', views.LessonCreateView.as_view(), name='create_lesson'),
    path('courses/<slug:course_slug>/lessons/<slug:lesson_slug>/', views.LessonDetailView.as_view(), name='lesson_detail'),
    path('lessons/<slug:lesson_slug>/edit/', views.LessonUpdateView.as_view(), name='edit_lesson'),
    path('lessons/<slug:lesson_slug>/delete/', views.LessonDeleteView.as_view(), name='delete_lesson'),
    
    # Resources
    path('resources/', views.ResourceListView.as_view(), name='resource_list'),
    path('resources/create/', views.ResourceCreateView.as_view(), name='create_resource'),
    path('resources/<int:resource_id>/edit/', views.ResourceUpdateView.as_view(), name='edit_resource'),
    path('resources/<int:resource_id>/delete/', views.ResourceDeleteView.as_view(), name='delete_resource'),
    
    # Language specific courses
    path('languages/<str:language_code>/courses/', views.LanguageCoursesView.as_view(), name='language_courses'),
]