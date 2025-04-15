from django.urls import path
from .views import (
    # Dashboard views
    DashboardsView, 
    # Chat view
    ChatView,
    # User Management views
    UserListView, UserTeachersView, UserStudentsView,
    UserViewAccountView, UserViewSecurityView, UserViewPreferencesView,
    # Access Management views
    AccessRolesView, AccessPermissionView,
    # Billing views
    BillingCreditsView, BillingHoursView, InvoiceListView, BillingReportsView
)
from django.contrib.auth.decorators import login_required


urlpatterns = [
    # 1. DASHBOARDS
    # Main dashboard (Overview)
    path(
        "",
        login_required(DashboardsView.as_view(template_name="dashboard_analytics.html")),
        name="overview",  # Changed from "index" to "overview" to match menu
    ),
    # Teacher dashboard
    path(
        "dashboard-teacher/",
        login_required(DashboardsView.as_view(template_name="dashboard_teacher.html")),
        name="teacher",  # Changed from "dashboard-teacher" to "teacher" to match menu
    ),
    # Student dashboard
    path(
        "dashboard-student/",
        login_required(DashboardsView.as_view(template_name="dashboard_student.html")),
        name="student",  # Changed from "dashboard-student" to "student" to match menu
    ),
    # Keep existing CRM dashboard for backward compatibility
    path(
        "dashboard/crm/",
        login_required(DashboardsView.as_view(template_name="dashboard_crm.html")),
        name="dashboard-crm",
    ),
    
    # 4. MESSAGING/CHAT
    # Chat/Messaging functionality
    path(
        "app/chat/",
        login_required(ChatView.as_view()),
        name="app-chat",
    ),
    
    # 5. USER MANAGEMENT
    # All Users
    path(
        "app/user/list/",
        login_required(UserListView.as_view()),
        name="app-user-list",
    ),
    # Teachers
    path(
        "app/user/teachers/",
        login_required(UserTeachersView.as_view()),
        name="app-user-teachers",
    ),
    # Students
    path(
        "app/user/students/",
        login_required(UserStudentsView.as_view()),
        name="app-user-students",
    ),
    # User Settings - Account
    path(
        "app/user/view/account/",
        login_required(UserViewAccountView.as_view()),
        name="app-user-view-account",
    ),
    # User Settings - Security
    path(
        "app/user/view/security/",
        login_required(UserViewSecurityView.as_view()),
        name="app-user-view-security",
    ),
    # User Settings - Preferences
    path(
        "app/user/view/preferences/",
        login_required(UserViewPreferencesView.as_view()),
        name="app-user-view-preferences",
    ),
    
    # 6. ROLES & PERMISSIONS
    # Roles
    path(
        "app/access/roles/",
        login_required(AccessRolesView.as_view()),
        name="app-access-roles",
    ),
    # Permissions
    path(
        "app/access/permission/",
        login_required(AccessPermissionView.as_view()),
        name="app-access-permission",
    ),
    
    # 7. BILLING & CREDITS
    # Credit Management
    path(
        "app/billing/credits/",
        login_required(BillingCreditsView.as_view()),
        name="app-billing-credits",
    ),
    # Hour Tracking
    path(
        "app/billing/hours/",
        login_required(BillingHoursView.as_view()),
        name="app-billing-hours",
    ),
    # Invoices
    path(
        "app/invoice/list/",
        login_required(InvoiceListView.as_view()),
        name="app-invoice-list",
    ),
    # Financial Reports
    path(
        "app/billing/reports/",
        login_required(BillingReportsView.as_view()),
        name="app-billing-reports",
    ),
]