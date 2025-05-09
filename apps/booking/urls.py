from django.urls import path
from . import views

app_name = 'booking'

urlpatterns = [
    # Booking dashboard
    path('', views.BookingDashboardView.as_view(), name='dashboard'),
    path('my-sessions/', views.MySessionsView.as_view(), name='my_sessions'),

    # Session management - unified approach
    path('sessions/create/', views.CreateSessionView.as_view(), name='create_session'),
    
    # Private session booking (legacy routes)
    path('private-sessions/book/<int:slot_id>/', views.BookPrivateSessionView.as_view(), name='book_private_session'),
    path('private-sessions/cancel/<int:slot_id>/', views.CancelPrivateSessionView.as_view(), name='cancel_private_session'),
    
    # Group session booking
    path('group-sessions/enroll/<int:session_id>/', views.EnrollGroupSessionView.as_view(), name='enroll_group_session'),
    path('group-sessions/unenroll/<int:session_id>/', views.UnenrollGroupSessionView.as_view(), name='unenroll_group_session'),
    
    # Credit management
    path('credits/purchase/', views.PurchaseCreditsView.as_view(), name='purchase_credits'),
    path('credits/history/', views.TransactionHistoryView.as_view(), name='transaction_history'),

    #slot management
    path('slots/create/', views.CreateSlotView.as_view(), name='create_slot'),
    path('slots/cancel/<int:slot_id>/', views.CancelBookingView.as_view(), name='cancel_booking'),
    path('slots/late-cancel/<int:slot_id>/', views.LateCancellationView.as_view(), name='late_cancellation'),
]