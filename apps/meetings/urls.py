from django.urls import path
from . import views

app_name = 'meetings'

urlpatterns = [
    # Meeting list and detail
    path('', views.MeetingListView.as_view(), name='meeting_list'),
    path('<int:meeting_id>/', views.MeetingDetailView.as_view(), name='meeting_detail'),
    
    # Create and edit meetings
    path('create/', views.CreateMeetingView.as_view(), name='create_meeting'),
    path('<int:meeting_id>/edit/', views.EditMeetingView.as_view(), name='edit_meeting'),
    path('<int:meeting_id>/cancel/', views.CancelMeetingView.as_view(), name='cancel_meeting'),
    
    # Send reminders
    path('<int:meeting_id>/remind/', views.SendReminderView.as_view(), name='send_reminder'),
    
    # Teacher availability
    path('availability/', views.AvailabilityListView.as_view(), name='availability_list'),
    path('availability/create/', views.CreateAvailabilityView.as_view(), name='create_availability'),
    path('availability/<int:availability_id>/delete/', views.DeleteAvailabilityView.as_view(), name='delete_availability'),
    
    # Calendar view
    path('calendar/', views.CalendarView.as_view(), name='calendar'),
]