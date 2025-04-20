from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

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