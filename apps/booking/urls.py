from django.urls import path
from . import views

app_name = 'booking'

urlpatterns = [
    path('', views.booking_dashboard, name='dashboard'),
    path('slots/create/', views.create_booking_slot, name='create_slot'),
    path('slots/<int:slot_id>/book/', views.book_slot, name='book_slot'),
    path('slots/<int:slot_id>/cancel/', views.cancel_booking, name='cancel_booking'),
    path('credits/purchase/', views.purchase_credits, name='purchase_credits'),
    path('credits/history/', views.transaction_history, name='transaction_history'),
]