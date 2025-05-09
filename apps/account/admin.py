from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _
from .models import (
    CustomUser, Profile, Role, UserRole, Notification, 
    ContactMessage, Subscriber, LoginHistory
)

class ProfileInline(admin.StackedInline):
    """Inline admin for user profiles"""
    model = Profile
    can_delete = False
    verbose_name_plural = 'Profile'
    fk_name = 'user'

class CustomUserAdmin(UserAdmin):
    """Admin class for the CustomUser model"""
    list_display = ('username', 'email', 'first_name', 'last_name', 'user_type', 
                   'is_verified', 'is_staff', 'is_superuser', 'date_joined', 'created_by_admin')
    list_filter = ('user_type', 'is_verified', 'is_staff', 'is_superuser', 'date_joined', 'created_by_admin', 'first_login')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('-date_joined',)
    readonly_fields = ('date_joined', 'last_login')
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'email')}),
        (_('Account info'), {'fields': ('user_type', 'is_verified', 'verification_token',
                                       'reset_password_token', 'reset_password_expiry',
                                       'first_login', 'created_by_admin')}),
        (_('Permissions'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2', 'user_type', 'created_by_admin', 'is_verified'),
        }),
    )
    
    inlines = [ProfileInline]
    
    def save_model(self, request, obj, form, change):
        """
        Override save_model to ensure superusers are always verified
        and to properly set created_by_admin flag
        """
        if not change:  # If this is a new user creation
            obj.created_by_admin = True
        
        if obj.is_superuser:
            obj.is_verified = True
            obj.verification_token = None
        
        super().save_model(request, obj, form, change)

class RoleAdmin(admin.ModelAdmin):
    """Admin class for the Role model"""
    list_display = ('name', 'description', 'permission_count', 'created_at')
    search_fields = ('name', 'description')
    filter_horizontal = ('permissions',)
    
    def permission_count(self, obj):
        return obj.permissions.count()
    permission_count.short_description = 'Permissions'

class UserRoleAdmin(admin.ModelAdmin):
    """Admin class for the UserRole model"""
    list_display = ('user', 'role', 'assigned_at', 'assigned_by')
    list_filter = ('role', 'assigned_at')
    search_fields = ('user__username', 'user__email', 'role__name')
    raw_id_fields = ('user', 'role', 'assigned_by')
    
    def save_model(self, request, obj, form, change):
        """Set assigned_by to current user if not already set"""
        if not obj.assigned_by:
            obj.assigned_by = request.user
        super().save_model(request, obj, form, change)

class NotificationAdmin(admin.ModelAdmin):
    """Admin class for the Notification model"""
    list_display = ('recipient', 'title', 'notification_type', 'read', 'created_at')
    list_filter = ('notification_type', 'read', 'created_at')
    search_fields = ('recipient__username', 'recipient__email', 'title', 'message')
    raw_id_fields = ('recipient', 'sender', 'content_type')
    
    fieldsets = (
        (None, {'fields': ('recipient', 'sender', 'notification_type', 'title', 'message')}),
        (_('Status'), {'fields': ('read', 'created_at')}),
        (_('Related Content'), {'fields': ('content_type', 'object_id', 'action_url')}),
    )
    
    readonly_fields = ('created_at',)
    
    actions = ['mark_as_read', 'mark_as_unread']
    
    def mark_as_read(self, request, queryset):
        queryset.update(read=True)
    mark_as_read.short_description = "Mark selected notifications as read"
    
    def mark_as_unread(self, request, queryset):
        queryset.update(read=False)
    mark_as_unread.short_description = "Mark selected notifications as unread"

class ContactMessageAdmin(admin.ModelAdmin):
    """Admin class for the ContactMessage model"""
    list_display = ('name', 'email', 'subject', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('name', 'email', 'subject', 'message')
    readonly_fields = ('created_at', 'updated_at')
    
    actions = ['mark_as_in_progress', 'mark_as_completed']
    
    def mark_as_in_progress(self, request, queryset):
        queryset.update(status='in_progress')
    mark_as_in_progress.short_description = "Mark selected messages as in progress"
    
    def mark_as_completed(self, request, queryset):
        queryset.update(status='completed')
    mark_as_completed.short_description = "Mark selected messages as completed"

class SubscriberAdmin(admin.ModelAdmin):
    """Admin class for the Subscriber model"""
    list_display = ('email', 'subscribed_at', 'is_active')
    list_filter = ('is_active', 'subscribed_at')
    search_fields = ('email',)
    readonly_fields = ('subscribed_at',)
    
    actions = ['activate_subscribers', 'deactivate_subscribers']
    
    def activate_subscribers(self, request, queryset):
        queryset.update(is_active=True)
    activate_subscribers.short_description = "Activate selected subscribers"
    
    def deactivate_subscribers(self, request, queryset):
        queryset.update(is_active=False)
    deactivate_subscribers.short_description = "Deactivate selected subscribers"

class LoginHistoryAdmin(admin.ModelAdmin):
    """Admin class for the LoginHistory model"""
    list_display = ('user', 'login_time', 'ip_address', 'location', 'was_first_login')
    list_filter = ('login_time', 'was_first_login')
    search_fields = ('user__username', 'user__email', 'ip_address', 'location')
    readonly_fields = ('login_time',)

# Register models
admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Role, RoleAdmin)
admin.site.register(UserRole, UserRoleAdmin)
admin.site.register(Notification, NotificationAdmin)
admin.site.register(ContactMessage, ContactMessageAdmin)
admin.site.register(Subscriber, SubscriberAdmin)
admin.site.register(LoginHistory, LoginHistoryAdmin)