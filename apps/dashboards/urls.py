from django.urls import path
from .views import (
    # Dashboard views
    DashboardOverviewView,
    TeacherDashboardView,
    StudentDashboardView,
 
    
)

# If you're using app_name, make sure it's consistent throughout your project
app_name = 'dashboards'   

urlpatterns = [
    # 1. DASHBOARDS
    # Main dashboard (Overview)
    path(
        "",
        DashboardOverviewView.as_view(),
        name="overview",  
    ),
    
    # Teacher dashboard - IMPORTANT: This name must match what's used in redirect()
    path(
        "dashboard-teacher/",
        TeacherDashboardView.as_view(),
        name="dashboard-teacher",  # This should match what's used in the TeacherDashboardView
    ),
    
    # Student dashboard - IMPORTANT: This name must match what's used in redirect()
    path(
        "dashboard-student/",
        StudentDashboardView.as_view(),
        name="dashboard-student",  # This should match what's used in the StudentDashboardView
    ),
    
    # Keep existing CRM dashboard for backward compatibility
    # path(
    #    "dashboard/crm/",
    #    DashboardsView.as_view(template_name="dashboard_crm.html"),
    #    name="dashboard-crm",
    #),
    
    # Other URL patterns...
    # ...
]