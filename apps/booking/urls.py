from django.urls import path
from . import views

app_name = 'booking'

urlpatterns = [
    path('', views.BookingDashboardView.as_view(), name='dashboard'),
    path('slots/create/', views.CreateBookingSlotView.as_view(), name='create_slot'),
    path('slots/<int:slot_id>/book/', views.BookSlotView.as_view(), name='book_slot'),
    path('slots/<int:slot_id>/cancel/', views.CancelBookingView.as_view(), name='cancel_booking'),
    path('credits/purchase/', views.PurchaseCreditsView.as_view(), name='purchase_credits'),
    path('credits/history/', views.TransactionHistoryView.as_view(), name='transaction_history'),
    path('credits/insufficient/', views.InsufficientCreditsView.as_view(), name='insufficient_credits'),
    path('slots/<int:slot_id>/late-cancellation/', views.LateCancellationView.as_view(), name='late_cancellation'),
]