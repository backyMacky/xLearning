from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from .models import Notification, NotificationType
import logging

logger = logging.getLogger(__name__)

class NotificationService:
    """Service for managing notifications"""
    
    @staticmethod
    def send_notification(recipient, title, message, notification_type=NotificationType.INFO,
                        sender=None, related_object=None, action_url=None):
        """
        Send a notification to a user
        
        Args:
            recipient: User object to receive the notification
            title: Notification title
            message: Notification message content
            notification_type: Type of notification from NotificationType choices
            sender: User object who sent the notification (optional)
            related_object: Related model instance (optional)
            action_url: URL to redirect to when notification is clicked (optional)
            
        Returns:
            Created notification object or None if failed
        """
        try:
            # Create notification
            notification = Notification(
                recipient=recipient,
                title=title,
                message=message,
                notification_type=notification_type,
                sender=sender,
                action_url=action_url
            )
            
            # Set related object if provided
            if related_object:
                content_type = ContentType.objects.get_for_model(related_object)
                notification.content_type = content_type
                notification.object_id = related_object.id
            
            notification.save()
            
            # Here you could add real-time notification via WebSockets if implemented
            # For now, the notification will be retrieved when user refreshes or checks notifications
            
            return notification
        
        except Exception as e:
            logger.error(f"Failed to send notification: {str(e)}")
            return None
    
    @staticmethod
    def send_notification_to_multiple(recipients, title, message, notification_type=NotificationType.INFO,
                                    sender=None, related_object=None, action_url=None):
        """
        Send the same notification to multiple users
        
        Args:
            recipients: List of User objects or QuerySet of Users
            title, message, etc: Same as send_notification method
            
        Returns:
            List of created notification objects
        """
        notifications = []
        for recipient in recipients:
            notification = NotificationService.send_notification(
                recipient=recipient,
                title=title,
                message=message,
                notification_type=notification_type,
                sender=sender,
                related_object=related_object,
                action_url=action_url
            )
            if notification:
                notifications.append(notification)
        
        return notifications
    
    @staticmethod
    def mark_as_read(notification_id, user):
        """
        Mark a notification as read
        
        Args:
            notification_id: ID of notification to mark as read
            user: User attempting to mark notification as read
            
        Returns:
            True if successful, False otherwise
        """
        try:
            notification = Notification.objects.get(id=notification_id, recipient=user)
            notification.mark_as_read()
            return True
        except Notification.DoesNotExist:
            return False
    
    @staticmethod
    def mark_all_as_read(user):
        """
        Mark all notifications for a user as read
        
        Args:
            user: User whose notifications to mark as read
            
        Returns:
            Number of notifications marked as read
        """
        return Notification.objects.filter(recipient=user, read=False).update(read=True)
    
    @staticmethod
    def delete_notification(notification_id, user):
        """
        Delete a notification
        
        Args:
            notification_id: ID of notification to delete
            user: User attempting to delete notification
            
        Returns:
            True if successful, False otherwise
        """
        try:
            notification = Notification.objects.get(id=notification_id, recipient=user)
            notification.delete()
            return True
        except Notification.DoesNotExist:
            return False
    
    @staticmethod
    def get_unread_count(user):
        """
        Get count of unread notifications for a user
        
        Args:
            user: User to get unread notification count for
            
        Returns:
            Count of unread notifications
        """
        return Notification.objects.filter(recipient=user, read=False).count()
