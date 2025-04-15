from django.views.generic import TemplateView
from web_project import TemplateLayout


"""
This file is a view controller for multiple pages as a module.
Here you can override the page view layout.
Refer to dashboards/urls.py file for more pages.
"""

class DashboardsView(TemplateView):
    # Predefined function
    def get_context_data(self, **kwargs):
        # A function to init the global layout. It is defined in web_project/__init__.py file
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        # Check which dashboard is being displayed
        if self.template_name == "dashboard_analytics.html":
            context['dashboard_type'] = 'overview'
        elif self.template_name == "dashboard_teacher.html":
            context['dashboard_type'] = 'teacher'
        elif self.template_name == "dashboard_student.html":
            context['dashboard_type'] = 'student'
        elif self.template_name == "dashboard_crm.html":
            context['dashboard_type'] = 'crm'
            
        return context


class ChatView(TemplateView):
    """
    View for the messaging/chat functionality
    """
    template_name = "app_chat.html"
    
    def get_context_data(self, **kwargs):
        # Initialize global layout
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        # Mock data for chat contacts
        context['contacts'] = [
            {
                'id': 1,
                'name': 'John Smith',
                'avatar': 'img/avatars/1.png',
                'status': 'online',
                'last_message': 'How are the revisions coming along?',
                'time': '10:12 AM',
                'unread': 2,
            },
            # More contacts...
        ]
        
        # Mock data for active chat
        context['active_chat'] = {
            'contact': context['contacts'][0],
            'messages': [
                # Messages...
            ]
        }
        
        return context


# User Management Views
class UserListView(TemplateView):
    """View for listing all users"""
    template_name = "app_user_list.html"
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        return context

class UserTeachersView(TemplateView):
    """View for listing teacher users"""
    template_name = "app_user_teachers.html"
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        return context

class UserStudentsView(TemplateView):
    """View for listing student users"""
    template_name = "app_user_students.html"
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        return context

class UserViewAccountView(TemplateView):
    """View for user account settings"""
    template_name = "app_user_view_account.html"
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        return context

class UserViewSecurityView(TemplateView):
    """View for user security settings"""
    template_name = "app_user_view_security.html"
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        return context

class UserViewPreferencesView(TemplateView):
    """View for user preferences settings"""
    template_name = "app_user_view_preferences.html"
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        return context


# Access Management Views
class AccessRolesView(TemplateView):
    """View for roles management"""
    template_name = "app_access_roles.html"
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        return context

class AccessPermissionView(TemplateView):
    """View for permission management"""
    template_name = "app_access_permission.html"
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        return context


# Billing Views
class BillingCreditsView(TemplateView):
    """View for credit management"""
    template_name = "app_billing_credits.html"
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        return context

class BillingHoursView(TemplateView):
    """View for hour tracking"""
    template_name = "app_billing_hours.html"
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        return context

class InvoiceListView(TemplateView):
    """View for invoice listing"""
    template_name = "app_invoice_list.html"
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        return context

class BillingReportsView(TemplateView):
    """View for financial reports"""
    template_name = "app_billing_reports.html"
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        return context