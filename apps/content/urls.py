from django.urls import path
from . import views

app_name = 'content'

urlpatterns = [
    # Home page - redirects to instructor listing
    path('', views.InstructorListView.as_view(), name='home'),
    
    # API endpoints (for compatibility with old code)
    path('api/courses/<int:course_id>/lessons/', views.get_course_lessons, name='api_course_lessons'),
    path('api/lessons/<int:lesson_id>/complete/', views.mark_lesson_complete, name='mark_lesson_complete'),
    
    # Instructor browsing views
    path('instructors/', views.InstructorListView.as_view(), name='instructor_list'),
    path('instructors/<str:username>/', views.InstructorDetailView.as_view(), name='instructor_detail'),
    path('instructors/<str:username>/reviews/', views.InstructorReviewsView.as_view(), name='instructor_reviews'),
    
    # Instructor profile management
    path('instructor-profile/create/', views.CreateInstructorProfileView.as_view(), name='create_instructor_profile'),
    path('instructor-profile/update/', views.UpdateInstructorProfileView.as_view(), name='update_instructor_profile'),
    
    # Instructor dashboard - match the name in menu json exactly
    path('instructor-dashboard/', views.InstructorDashboardView.as_view(), name='instructor_dashboard'),
    
    # Private session management (for instructors)
    path('private-sessions/create/', views.CreatePrivateSessionSlotView.as_view(), name='create_private_slot'),
    path('private-sessions/<int:slot_id>/edit/', views.UpdatePrivateSessionSlotView.as_view(), name='update_private_slot'),
    path('private-sessions/<int:slot_id>/delete/', views.DeletePrivateSessionSlotView.as_view(), name='delete_private_slot'),
    
    # Group session management (for instructors)
    path('group-sessions/create/', views.CreateGroupSessionView.as_view(), name='create_group_session'),
    path('group-sessions/<int:session_id>/edit/', views.UpdateGroupSessionView.as_view(), name='update_group_session'),
    path('group-sessions/<int:session_id>/delete/', views.DeleteGroupSessionView.as_view(), name='delete_group_session'),
    
    # Group session views (for students)
    path('group-sessions/', views.GroupSessionListView.as_view(), name='group_session_list'),
    path('group-sessions/<int:session_id>/', views.GroupSessionDetailView.as_view(), name='group_session_detail'),
    
    # Student dashboard
    path('student-dashboard/', views.StudentDashboardView.as_view(), name='student_dashboard'),
    
    # Reviews
    path('reviews/create/<int:instructor_id>/', views.CreateInstructorReviewView.as_view(), name='create_review'),
    path('reviews/create/<int:instructor_id>/<str:session_type>/<int:session_id>/', 
         views.CreateInstructorReviewView.as_view(), name='create_review_for_session'),
         
    # Legacy URLs - redirected to new views for backward compatibility
    path('courses/', views.RedirectToCourseListView.as_view(), name='course_list'),
    path('courses/<slug:slug>/', views.RedirectToCourseDetailView.as_view(), name='course_detail'),

    # Resource management
path('resources/', views.ResourceListView.as_view(), name='resource_list'),
path('resources/create/', views.CreateResourceView.as_view(), name='create_resource'),
path('resources/<int:resource_id>/edit/', views.UpdateResourceView.as_view(), name='edit_resource'),
path('resources/<int:resource_id>/delete/', views.DeleteResourceView.as_view(), name='delete_resource'),

# Session Feedback
path('feedback/create/<str:session_type>/<int:session_id>/', 
     views.CreateSessionFeedbackView.as_view(), name='create_feedback'),
path('feedback/list/', views.SessionFeedbackListView.as_view(), name='feedback_list'),

# Session Reports
path('reports/create/<str:session_type>/<int:session_id>/', 
     views.CreateSessionReportView.as_view(), name='create_report'),
path('reports/list/', views.SessionReportListView.as_view(), name='report_list'),
path('reports/<int:report_id>/', views.SessionReportDetailView.as_view(), name='report_detail'),

# Session Attendance
path('attendance/manage/<int:session_id>/', 
     views.ManageSessionAttendanceView.as_view(), name='manage_attendance'),

# Language management
path('languages/', views.LanguageListView.as_view(), name='language_list'),
path('languages/create/', views.LanguageCreateView.as_view(), name='create_language'),
path('languages/<int:language_id>/edit/', views.LanguageUpdateView.as_view(), name='edit_language'),

# Language level management
path('levels/', views.LanguageLevelListView.as_view(), name='language_level_list'),
path('levels/create/', views.LanguageLevelCreateView.as_view(), name='create_language_level'),
path('levels/<int:level_id>/edit/', views.LanguageLevelUpdateView.as_view(), name='edit_language_level'),     
]