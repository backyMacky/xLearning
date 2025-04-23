from django.urls import path
from . import views

app_name = 'content'

urlpatterns = [
    # Course management
    path('courses/', views.CourseListView.as_view(), name='course_list'),
    path('courses/create/', views.CreateCourseView.as_view(), name='create_course'),
    path('courses/<slug:slug>/', views.CourseDetailView.as_view(), name='course_detail'),
    path('courses/<slug:slug>/edit/', views.UpdateCourseView.as_view(), name='edit_course'),
    
    # Module management
    path('courses/<int:course_id>/modules/create/', views.CreateModuleView.as_view(), name='create_module'),
    path('modules/<int:module_id>/edit/', views.UpdateModuleView.as_view(), name='edit_module'),
    path('modules/<int:module_id>/delete/', views.DeleteModuleView.as_view(), name='delete_module'),
    
    # Lesson management
    path('modules/<int:module_id>/lessons/create/', views.CreateLessonView.as_view(), name='create_lesson'),
    path('lessons/<slug:lesson_slug>/edit/', views.UpdateLessonView.as_view(), name='edit_lesson'),
    path('lessons/<slug:lesson_slug>/delete/', views.DeleteLessonView.as_view(), name='delete_lesson'),
    path('courses/<slug:course_slug>/lessons/<slug:lesson_slug>/', views.LessonDetailView.as_view(), name='lesson_detail'),
    path('lessons/<int:lesson_id>/complete/', views.mark_lesson_complete, name='mark_lesson_complete'),
    
    # Resource management
    path('resources/', views.ResourceListView.as_view(), name='resource_list'),
    path('resources/create/', views.CreateResourceView.as_view(), name='create_resource'),
    path('resources/<int:resource_id>/edit/', views.UpdateResourceView.as_view(), name='edit_resource'),
    path('resources/<int:resource_id>/delete/', views.DeleteResourceView.as_view(), name='delete_resource'),
    
    # Instructor management
    path('instructors/', views.InstructorListView.as_view(), name='instructor_list'),
    path('instructors/<str:username>/', views.InstructorDetailView.as_view(), name='instructor_detail'),
    path('instructors/<str:username>/reviews/', views.InstructorReviewsView.as_view(), name='instructor_reviews'),
    path('instructors/<int:instructor_id>/review/', views.CreateInstructorReviewView.as_view(), name='create_review'),
    path('instructors/<int:instructor_id>/review/<str:session_type>/<int:session_id>/', 
         views.CreateInstructorReviewView.as_view(), name='create_review_for_session'),
    
    # Instructor profile management
    path('instructor-profile/create/', views.CreateInstructorProfileView.as_view(), name='create_instructor_profile'),
    path('instructor-profile/update/', views.UpdateInstructorProfileView.as_view(), name='update_instructor_profile'),
    path('instructor-dashboard/', views.InstructorDashboardView.as_view(), name='instructor_dashboard'),
    
    # Private session management
    path('private-sessions/create/', views.CreatePrivateSessionView.as_view(), name='create_private_session'),
    path('private-sessions/<int:session_id>/edit/', views.UpdatePrivateSessionView.as_view(), name='update_private_session'),
    path('private-sessions/<int:session_id>/delete/', views.DeletePrivateSessionView.as_view(), name='delete_private_session'),
    
    # Group session management
    path('group-sessions/create/', views.CreateGroupSessionView.as_view(), name='create_group_session'),
    path('group-sessions/<int:session_id>/edit/', views.UpdateGroupSessionView.as_view(), name='update_group_session'),
    path('group-sessions/<int:session_id>/delete/', views.DeleteGroupSessionView.as_view(), name='delete_group_session'),
    
    # Group session views (for students)
    path('group-sessions/', views.GroupSessionListView.as_view(), name='group_session_list'),
    path('group-sessions/<int:session_id>/', views.GroupSessionDetailView.as_view(), name='group_session_detail'),
    
    # Student dashboard
    path('student-dashboard/', views.StudentDashboardView.as_view(), name='student_dashboard'),
    
    # Session feedback
    path('feedback/create/<str:session_type>/<int:session_id>/', 
         views.CreateSessionFeedbackView.as_view(), name='create_feedback'),
    path('feedback/list/', views.SessionFeedbackListView.as_view(), name='feedback_list'),
    
    # API endpoints
    path('api/courses/<int:course_id>/lessons/', views.get_course_lessons, name='api_course_lessons'),
    path('api/session-preview/', views.session_preview_data, name='session_preview_data'),
    path('api/meeting-link/<str:session_type>/<int:session_id>/', views.get_meeting_link, name='get_meeting_link'),
]