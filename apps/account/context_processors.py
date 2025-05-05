
from .services import NotificationService

def notification_context(request):
    """
    Context processor to add notification data to all template contexts
    
    Args:
        request: The current request
    
    Returns:
        Dictionary with notification context data
    """
    context_data = {
        'notification_count': 0,
        'recent_notifications': []
    }
    
    try:
        # Only add notification data for authenticated users
        if hasattr(request, 'user') and request.user.is_authenticated:
            context_data['notification_count'] = NotificationService.get_unread_count(request.user)
            # Get 5 most recent notifications
            from .models import Notification
            context_data['recent_notifications'] = Notification.objects.filter(
                recipient=request.user
            ).order_by('-created_at')[:5]
    except Exception as e:
        # Handle database errors gracefully
        pass
    
    return context_data