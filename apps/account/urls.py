from django.urls import path
from . import views

app_name = 'account'

urlpatterns = [
    # Authentication URLs
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('forgot-password/', views.ForgotPasswordView.as_view(), name='forgot_password'),
    path('reset-password/<str:token>/', views.ResetPasswordView.as_view(), name='reset_password'),
    path('verify-email/', views.VerifyEmailView.as_view(), name='verify_email'),
    path('verify-email/<str:token>/', views.VerifyEmailView.as_view(), name='verify_email_confirm'),
    path('resend-verification/', views.ResendVerificationEmailView.as_view(), name='resend_verification'),
    
      # Instructor Management URLs
    path('admin/instructors/create/', views.CreateInstructorView.as_view(), name='create_instructor'),
    path('admin/instructors/approve/<int:user_id>/', views.ApproveInstructorRequestView.as_view(), name='approve_instructor_request'),
    
    # Profile URLs
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('profile/update/', views.UpdateProfileView.as_view(), name='update_profile'),
    path('profile/<str:username>/', views.ProfileView.as_view(), name='user_profile'),
    path('api/profile/', views.ProfileAPIView.as_view(), name='profile_api'),
    
    # Teacher Request URLs
    path('teacher-request/', views.TeacherRequestView.as_view(), name='teacher_request'),
    path('admin/user/<int:user_id>/teacher-approval/', views.TeacherApprovalView.as_view(), name='teacher_approval'),
    
    # Notification URLs
    path('notifications/', views.NotificationListView.as_view(), name='notification_list'),
    path('notifications/<int:pk>/', views.NotificationDetailView.as_view(), name='notification_detail'),
    path('notifications/<int:pk>/redirect/', views.NotificationRedirectView.as_view(), name='notification_redirect'),
    path('notifications/<int:pk>/mark-read/', views.NotificationMarkReadView.as_view(), name='notification_mark_read'),
    path('notifications/mark-all-read/', views.NotificationMarkAllReadView.as_view(), name='notification_mark_all_read'),
    path('notifications/<int:pk>/delete/', views.NotificationDeleteView.as_view(), name='notification_delete'),
    path('api/notifications/count/', views.NotificationCountView.as_view(), name='notification_count'),
    
    # User Management URLs
    path('admin/users/', views.UserListView.as_view(), name='user_list'),
    path('admin/users/create/', views.UserCreateView.as_view(), name='user_create'),
    path('admin/users/<int:pk>/', views.UserDetailView.as_view(), name='user_detail'),
    path('admin/users/<int:pk>/edit/', views.UserEditView.as_view(), name='user_edit'),
    path('admin/users/<int:pk>/delete/', views.UserDeleteView.as_view(), name='user_delete'),
    
    # Role Management URLs
    path('admin/roles/', views.RoleListView.as_view(), name='role_list'),
    path('admin/roles/create/', views.RoleCreateView.as_view(), name='role_create'),
    path('admin/roles/<int:pk>/', views.RoleDetailView.as_view(), name='role_detail'),
    path('admin/roles/<int:pk>/edit/', views.RoleEditView.as_view(), name='role_edit'),
    path('admin/roles/<int:pk>/delete/', views.RoleDeleteView.as_view(), name='role_delete'),
    
    # Permission Management URLs
    path('admin/permissions/', views.PermissionListView.as_view(), name='permission_list'),
    
    # User Roles Management URLs
    path('admin/users/<int:pk>/roles/', views.UserRolesView.as_view(), name='user_roles'),
    path('admin/users/<int:pk>/roles/add/', views.UserRoleAddView.as_view(), name='user_role_add'),
    path('admin/users/<int:pk>/roles/<int:role_id>/remove/', views.UserRoleRemoveView.as_view(), name='user_role_remove'),
    
    # User Settings URLs
    path('settings/security/', views.SecuritySettingsView.as_view(), name='security_settings'),
    path('settings/preferences/', views.PreferencesView.as_view(), name='preferences'),
    path('settings/', views.AccountSettingsView.as_view(), name='account_settings'),

    # Footer URLs
  path('license/', views.LicenseView.as_view(), name='license'),
  path('more-themes/', views.MoreThemesView.as_view(), name='more_themes'),
  path('documentation/', views.DocumentationView.as_view(), name='documentation'),
  path('support/', views.SupportView.as_view(), name='support'),
]