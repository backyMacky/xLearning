from django.urls import path
from . import views

app_name = 'meetings'

urlpatterns = [
    path('', views.meeting_list, name='meeting_list'),
    path('<int:meeting_id>/', views.meeting_detail, name='meeting_detail'),
    path('create/', views.create_meeting, name='create_meeting'),
    path('<int:meeting_id>/edit/', views.edit_meeting, name='edit_meeting'),
    path('<int:meeting_id>/cancel/', views.cancel_meeting, name='cancel_meeting'),
    path('<int:meeting_id>/remind/', views.send_meeting_reminder, name='send_reminder'),
    path('availability/', views.availability_list, name='availability_list'),
    path('availability/create/', views.create_availability, name='create_availability'),
    path('availability/<int:availability_id>/delete/', views.delete_availability, name='delete_availability'),
]