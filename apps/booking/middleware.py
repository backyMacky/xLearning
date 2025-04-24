from django.db import connection
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class DuplicateSessionCleanupMiddleware:
    """
    Middleware to clean up duplicate session records that can cause MultipleObjectsReturned errors.
    This middleware executes a database query to remove duplicate private sessions and group sessions.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        # Run session cleanup on startup if enabled
        if getattr(settings, 'CLEAN_DUPLICATE_SESSIONS_ON_STARTUP', False):
            self.clean_duplicate_sessions()
    
    def __call__(self, request):
        # Process request and return response as normal
        response = self.get_response(request)
        return response
        
    def clean_duplicate_sessions(self):
        """
        Clean up duplicate sessions in the database by identifying duplicates and keeping only one copy.
        """
        try:
            # Clean up private sessions
            self._clean_private_sessions()
            
            # Clean up group sessions 
            self._clean_group_sessions()
            
            logger.info("Session cleanup completed successfully")
        except Exception as e:
            logger.error(f"Error during session cleanup: {str(e)}")
    
    def _clean_private_sessions(self):
        """
        Clean up duplicate private sessions in content app
        """
        try:
            from apps.content.models import PrivateSession
            
            # Get all private sessions
            all_sessions = PrivateSession.objects.all()
            
            # Group by instructor and start_time to find duplicates
            from django.db.models import Count
            duplicates = PrivateSession.objects.values('instructor', 'start_time') \
                .annotate(count=Count('id')) \
                .filter(count__gt=1)
            
            # Process each group of duplicates
            for dup in duplicates:
                # Get all sessions with this instructor and start_time
                sessions = PrivateSession.objects.filter(
                    instructor=dup['instructor'],
                    start_time=dup['start_time']
                ).order_by('id')
                
                # Keep the first one and delete the rest
                first_session = sessions.first()
                to_delete = sessions.exclude(id=first_session.id)
                
                logger.info(f"Deleting {to_delete.count()} duplicate private sessions for instructor #{dup['instructor']} at {dup['start_time']}")
                to_delete.delete()
        
        except (ImportError, AttributeError):
            # Content app not available or models not compatible
            logger.debug("Content app PrivateSession model not available")
        
        # Also clean duplicates in booking app
        try:
            from apps.booking.models import PrivateSessionSlot
            
            # Group by instructor and start_time to find duplicates
            from django.db.models import Count
            duplicates = PrivateSessionSlot.objects.values('instructor', 'start_time') \
                .annotate(count=Count('id')) \
                .filter(count__gt=1)
            
            # Process each group of duplicates
            for dup in duplicates:
                # Get all slots with this instructor and start_time
                slots = PrivateSessionSlot.objects.filter(
                    instructor=dup['instructor'],
                    start_time=dup['start_time']
                ).order_by('id')
                
                # Keep the first one and delete the rest
                first_slot = slots.first()
                to_delete = slots.exclude(id=first_slot.id)
                
                logger.info(f"Deleting {to_delete.count()} duplicate booking slots for instructor #{dup['instructor']} at {dup['start_time']}")
                to_delete.delete()
        
        except (ImportError, AttributeError):
            # Booking app not available or models not compatible
            logger.debug("Booking app PrivateSessionSlot model not available")
    
    def _clean_group_sessions(self):
        """
        Clean up duplicate group sessions in content app
        """
        try:
            from apps.content.models import GroupSession
            
            # Group by instructor, title, and start_time to find duplicates
            from django.db.models import Count
            duplicates = GroupSession.objects.values('instructor', 'title', 'start_time') \
                .annotate(count=Count('id')) \
                .filter(count__gt=1)
            
            # Process each group of duplicates
            for dup in duplicates:
                # Get all sessions with this instructor, title, and start_time
                sessions = GroupSession.objects.filter(
                    instructor=dup['instructor'],
                    title=dup['title'],
                    start_time=dup['start_time']
                ).order_by('id')
                
                # Keep the first one and delete the rest
                first_session = sessions.first()
                to_delete = sessions.exclude(id=first_session.id)
                
                logger.info(f"Deleting {to_delete.count()} duplicate group sessions for instructor #{dup['instructor']} at {dup['start_time']}")
                to_delete.delete()
        
        except (ImportError, AttributeError):
            # Content app not available or models not compatible
            logger.debug("Content app GroupSession model not available")
        
        # Also clean duplicates in booking app
        try:
            from apps.booking.models import GroupSession as BookingGroupSession
            
            # Group by instructor, title, and start_time to find duplicates
            from django.db.models import Count
            duplicates = BookingGroupSession.objects.values('instructor', 'title', 'start_time') \
                .annotate(count=Count('id')) \
                .filter(count__gt=1)
            
            # Process each group of duplicates
            for dup in duplicates:
                # Get all sessions with this instructor, title, and start_time
                sessions = BookingGroupSession.objects.filter(
                    instructor=dup['instructor'],
                    title=dup['title'],
                    start_time=dup['start_time']
                ).order_by('id')
                
                # Keep the first one and delete the rest
                first_session = sessions.first()
                to_delete = sessions.exclude(id=first_session.id)
                
                logger.info(f"Deleting {to_delete.count()} duplicate booking group sessions for instructor #{dup['instructor']} at {dup['start_time']}")
                to_delete.delete()
        
        except (ImportError, AttributeError):
            # Booking app not available or models not compatible
            logger.debug("Booking app GroupSession model not available")

# Management command to clean up sessions
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Clean up duplicate sessions in the database'
    
    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('Starting session cleanup...'))
        
        middleware = DuplicateSessionCleanupMiddleware(get_response=None)
        middleware.clean_duplicate_sessions()
        
        self.stdout.write(self.style.SUCCESS('Session cleanup completed successfully'))