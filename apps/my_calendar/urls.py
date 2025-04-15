from django.urls import path
from .views import (
    CalendarViewView,
    CalendarSessionsView,
    CalendarAvailabilityView,
    CalendarHistoryView
)
from django.contrib.auth.decorators import login_required

urlpatterns = [
    # My Schedule view
    path(
        "app/calendar/view/",
        login_required(CalendarViewView.as_view()),
        name="app-calendar-view",
    ),
    
    # Live Sessions view
    path(
        "app/calendar/sessions/",
        login_required(CalendarSessionsView.as_view()),
        name="app-calendar-sessions",
    ),
    
    # Set Availability view
    path(
        "app/calendar/availability/",
        login_required(CalendarAvailabilityView.as_view()),
        name="app-calendar-availability",
    ),
    
    # Session History view
    path(
        "app/calendar/history/",
        login_required(CalendarHistoryView.as_view()),
        name="app-calendar-history",
    ),
]