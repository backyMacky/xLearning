from django.db import models
from django.contrib.auth.models import User, AbstractUser, Permission, Group
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse

class UserType(models.TextChoices):
    TEACHER = 'teacher', 'Teacher'
    STUDENT = 'student', 'Student'
    ADMIN = 'admin', 'Administrator'


# Add fields to User model
User.add_to_class('user_type', models.CharField(max_length=20, choices=UserType.choices, default=UserType.STUDENT))
User.add_to_class('is_verified', models.BooleanField(default=False))
User.add_to_class('verification_token', models.CharField(max_length=100, blank=True, null=True))
User.add_to_class('reset_password_token', models.CharField(max_length=100, blank=True, null=True))
User.add_to_class('reset_password_expiry', models.DateTimeField(blank=True, null=True))
# for testing skipp user check temporarily
def is_teacher(self):
    return self.user_type == UserType.TEACHER

def is_student(self):
    return self.user_type == UserType.STUDENT

def is_admin(self):
    return self.user_type == UserType.ADMIN

User.add_to_class('is_teacher', property(is_teacher))
User.add_to_class('is_student', property(is_student))
User.add_to_class('is_admin', property(is_admin))


# Role and Permission management
class Role(models.Model):
    """Model for custom roles with specific permissions"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    permissions = models.ManyToManyField(Permission, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name

class UserRole(models.Model):
    """Model to assign roles to users"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_roles')
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    assigned_at = models.DateTimeField(auto_now_add=True)
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='role_assignments')
    
    class Meta:
        unique_together = ('user', 'role')
        
    def __str__(self):
        return f"{self.user.username} - {self.role.name}"

# Update the Profile model to support additional fields
class Profile(models.Model):
    """Extended user profile information"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    native_language = models.CharField(max_length=50, blank=True, null=True)
    learning_language = models.CharField(max_length=50, blank=True, null=True)
    profile_image = models.ImageField(upload_to='profile_images/', null=True, blank=True)
    bio = models.TextField(blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.user.username}'s Profile"
    
    def get_profile(self):
        """Return profile data in a dictionary format"""
        return {
            'id': self.id,
            'username': self.user.username,
            'email': self.user.email,
            'native_language': self.native_language,
            'learning_language': self.learning_language,
            'profile_image': self.profile_image.url if self.profile_image else None,
            'is_teacher': self.user.user_type == UserType.TEACHER,
            'is_student': self.user.user_type == UserType.STUDENT,
            'is_admin': self.user.user_type == UserType.ADMIN,
            'is_verified': self.user.is_verified,
            'bio': self.bio,
            'phone_number': self.phone_number,
            'date_of_birth': self.date_of_birth,
        }
    
    class Meta:
        app_label = 'account'

# Function to authenticate with email
def authenticate_with_email(email, password):
    """Custom authenticate function that uses email instead of username"""
    try:
        user = User.objects.get(email=email)
        if user.check_password(password):
            return user
    except User.DoesNotExist:
        pass
    return None

# Create Profile automatically when a User is created
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()


class NotificationType(models.TextChoices):
    """Types of notifications in the system"""
    INFO = 'info', 'Information'
    SUCCESS = 'success', 'Success'
    WARNING = 'warning', 'Warning'
    DANGER = 'danger', 'Danger'
    SYSTEM = 'system', 'System'
    ACHIEVEMENT = 'achievement', 'Achievement'
    MESSAGE = 'message', 'Message'
    CONNECTION = 'connection', 'Connection'
    ORDER = 'order', 'Order'

class Notification(models.Model):
    """Model for storing user notifications"""
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='sent_notifications')
    notification_type = models.CharField(max_length=20, choices=NotificationType.choices, default=NotificationType.INFO)
    title = models.CharField(max_length=255)
    message = models.TextField()
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Optional link to related object (polymorphic relationship)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    related_object = GenericForeignKey('content_type', 'object_id')
    
    # Optional URL to redirect to when clicked
    action_url = models.CharField(max_length=255, blank=True, null=True)
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return f"Notification to {self.recipient.username}: {self.title}"
    
    def mark_as_read(self):
        """Mark notification as read"""
        self.read = True
        self.save()
    
    def get_absolute_url(self):
        """Get URL to view notification detail"""
        return reverse('account:notification_detail', kwargs={'pk': self.pk})
    
    def get_action_url(self):
        """Get URL for notification action"""
        if self.action_url:
            return self.action_url
        # If no action URL, try to generate one based on related object
        if self.related_object and hasattr(self.related_object, 'get_absolute_url'):
            return self.related_object.get_absolute_url()
        return None    