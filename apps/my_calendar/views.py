from django.views.generic import TemplateView
from web_project import TemplateLayout


"""
This file is a view controller for multiple pages as a module.
Here you can override the page view layout.
Refer to my_calendar/urls.py file for more pages.
"""


class CalendarView(TemplateView):
    """Base calendar view class"""
    
    def get_context_data(self, **kwargs):
        # A function to init the global layout. It is defined in web_project/__init__.py file
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        # Determine which calendar view is being displayed
        if self.template_name == "app_calendar.html":
            context['calendar_type'] = 'view'
        elif self.template_name == "app_calendar_sessions.html":
            context['calendar_type'] = 'sessions'
        elif self.template_name == "app_calendar_availability.html":
            context['calendar_type'] = 'availability'
        elif self.template_name == "app_calendar_history.html":
            context['calendar_type'] = 'history'
            
        return context


class CalendarViewView(CalendarView):
    """View for My Schedule calendar view"""
    template_name = "app_calendar.html"


class CalendarSessionsView(CalendarView):
    """View for Live Sessions calendar view"""
    template_name = "app_calendar_sessions.html"


class CalendarAvailabilityView(CalendarView):
    """View for Set Availability calendar view"""
    template_name = "app_calendar_availability.html"


class CalendarHistoryView(CalendarView):
    """View for Session History calendar view"""
    template_name = "app_calendar_history.html"