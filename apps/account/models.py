from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractUser, Permission, Group
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
import random
import string


class UserType(models.TextChoices):
    TEACHER = 'teacher', 'Teacher'
    STUDENT = 'student', 'Student'
    ADMIN = 'admin', 'Administrator'


class CustomUser(AbstractUser):
    """Custom User model extending Django's AbstractUser"""
    user_type = models.CharField(max_length=20, choices=UserType.choices, default=UserType.STUDENT)
    is_verified = models.BooleanField(
    default=False, help_text="Indicates if the user's email has been verified. Superusers are automatically verified.")
    verification_token = models.CharField(max_length=100, blank=True, null=True)
    reset_password_token = models.CharField(max_length=100, blank=True, null=True)
    reset_password_expiry = models.DateTimeField(blank=True, null=True)
    first_login = models.BooleanField(default=True)
    created_by_admin = models.BooleanField(default=False)
    instructor_approved_by = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='approved_instructors'
    )
    
    def is_teacher(self):
        return self.user_type == UserType.TEACHER
    
    def is_student(self):
        return self.user_type == UserType.STUDENT
    
    def is_admin(self):
        return self.user_type == UserType.ADMIN

    def __str__(self):
        return self.username
    
    def get_verified_status(self):
        """Get the verification status, considering superuser status"""
        return self.is_verified or self.is_superuser

    class Meta:
        swappable = 'AUTH_USER_MODEL'
        permissions = (
            ("can_manage_instructors", "Can manage instructor accounts"),
            ("can_view_all_users", "Can view all users"),
            ("can_approve_instructor_requests", "Can approve instructor applications"),
        )

        
class Profile(models.Model):
    """Extended user profile information"""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    native_language = models.CharField(max_length=50, blank=True, null=True)
    learning_language = models.CharField(max_length=50, blank=True, null=True)
    profile_image = models.ImageField(upload_to='profile_images/', null=True, blank=True)
    bio = models.TextField(blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    
    # Teacher request fields
    teacher_request_pending = models.BooleanField(default=False)
    teacher_request_date = models.DateTimeField(null=True, blank=True)
    teacher_approved_date = models.DateTimeField(null=True, blank=True)
    teacher_qualifications = models.TextField(blank=True, null=True)
    teacher_experience = models.TextField(blank=True, null=True)
    teacher_subjects = models.TextField(blank=True, null=True)
    
    # Purchase tracking
    has_purchased = models.BooleanField(default=False)
    password_changed_once = models.BooleanField(default=False)
    
    class Meta:
        app_label = 'account'

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
            'is_teacher': self.user.is_teacher(),
            'is_student': self.user.is_student(),
            'is_admin': self.user.is_admin(),
            'is_verified': self.user.is_verified,
            'bio': self.bio,
            'phone_number': self.phone_number,
            'date_of_birth': self.date_of_birth,
            'teacher_request_pending': self.teacher_request_pending,
            'teacher_request_date': self.teacher_request_date,
            'first_login': self.user.first_login,
            'created_by_admin': self.user.created_by_admin,
            'has_purchased': self.has_purchased
        }


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
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='user_roles')
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    assigned_at = models.DateTimeField(auto_now_add=True)
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='role_assignments')
    
    class Meta:
        unique_together = ('user', 'role')
        
    def __str__(self):
        return f"{self.user.username} - {self.role.name}"


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
    INSTRUCTOR_APPROVAL = 'instructor_approval', 'Instructor Approval'
    INSTRUCTOR_REJECTION = 'instructor_rejection', 'Instructor Rejection'
    ACCOUNT_CREATED = 'account_created', 'Account Created'


class Notification(models.Model):
    """Model for storing user notifications"""
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='sent_notifications')
    notification_type = models.CharField(max_length=30, choices=NotificationType.choices, default=NotificationType.INFO)
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


class ContactMessage(models.Model):
    """Model for storing contact form submissions"""
    
    class ContactStatus(models.TextChoices):
        NEW = 'new', _('New')
        IN_PROGRESS = 'in_progress', _('In Progress')
        COMPLETED = 'completed', _('Completed')
    
    name = models.CharField(max_length=100, verbose_name=_("Full Name"))
    email = models.EmailField(verbose_name=_("Email Address"))
    subject = models.CharField(max_length=200, verbose_name=_("Subject"))
    message = models.TextField(verbose_name=_("Message"))
    status = models.CharField(
        max_length=20, 
        choices=ContactStatus.choices, 
        default=ContactStatus.NEW,
        verbose_name=_("Status")
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated At"))
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = _("Contact Message")
        verbose_name_plural = _("Contact Messages")
    
    def __str__(self):
        return f"{self.name} - {self.subject} ({self.created_at.strftime('%Y-%m-%d')})"


class Subscriber(models.Model):
    """Model for storing newsletter subscribers"""
    email = models.EmailField(unique=True, verbose_name=_("Email Address"))
    subscribed_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Subscribed At"))
    is_active = models.BooleanField(default=True, verbose_name=_("Active"))
    
    class Meta:
        ordering = ['-subscribed_at']
        verbose_name = _("Subscriber")
        verbose_name_plural = _("Subscribers")
    
    def __str__(self):
        return self.email


class LoginHistory(models.Model):
    """Track user login history for security purposes"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='login_history')
    login_time = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)
    device_info = models.CharField(max_length=200, blank=True, null=True)
    location = models.CharField(max_length=200, blank=True, null=True)
    was_first_login = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.user.username} - {self.login_time}"
    
    class Meta:
        ordering = ['-login_time']
        verbose_name = _("Login History")
        verbose_name_plural = _("Login Histories")


# Create Profile automatically when a User is created
@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)


@receiver(post_save, sender=settings.AUTH_USER_MODEL)  
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def set_superuser_verified(sender, instance, created, **kwargs):
    """Ensure superusers are automatically verified"""
    if instance.is_superuser and not instance.is_verified:
        # Update is_verified without triggering the full save
        # to avoid potential recursion with other signals
        type(instance).objects.filter(pk=instance.pk).update(is_verified=True)
        
        # If this is a new superuser, also clear any verification token
        if created and instance.verification_token:
            type(instance).objects.filter(pk=instance.pk).update(verification_token=None)

# Password generation utility
def generate_random_password(length=12):
    """Generate a random password for admin-created accounts"""
    characters = string.ascii_letters + string.digits + string.punctuation
    return ''.join(random.choice(characters) for _ in range(length))


# Utility function to check if user needs to change password
def should_change_password(user):
    """Check if a user should change their password"""
    if user.created_by_admin and not user.profile.password_changed_once:
        return True
    return False