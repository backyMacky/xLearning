from django.contrib import admin
from .models import (
    Instructor, InstructorSpecialty, InstructorQualification, InstructorExperience,
    PrivateSessionSlot, GroupSession, InstructorReview, CreditTransaction
)

@admin.register(Instructor)
class InstructorAdmin(admin.ModelAdmin):
    list_display = ('user', 'is_featured', 'is_available', 'hourly_rate', 'rating', 'sessions_completed')
    list_filter = ('is_featured', 'is_available')
    search_fields = ('user__username', 'user__email', 'teaching_languages')
    readonly_fields = ('rating', 'review_count', 'sessions_completed')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'bio', 'profile_image')
        }),
        ('Teaching Information', {
            'fields': ('teaching_languages', 'specialties', 'hourly_rate', 'teaching_style')
        }),
        ('Status', {
            'fields': ('is_featured', 'is_available', 'availability_last_updated')
        }),
        ('Statistics', {
            'classes': ('collapse',),
            'fields': ('rating', 'review_count', 'sessions_completed')
        }),
    )

@admin.register(InstructorSpecialty)
class InstructorSpecialtyAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'description')

@admin.register(InstructorQualification)
class InstructorQualificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'instructor', 'institution', 'year')
    list_filter = ('year',)
    search_fields = ('title', 'instructor__user__username', 'institution')

@admin.register(InstructorExperience)
class InstructorExperienceAdmin(admin.ModelAdmin):
    list_display = ('position', 'instructor', 'institution', 'years')
    search_fields = ('position', 'instructor__user__username', 'institution')

@admin.register(PrivateSessionSlot)
class PrivateSessionSlotAdmin(admin.ModelAdmin):
    list_display = ('instructor', 'student', 'start_time', 'end_time', 'language', 'level', 'status')
    list_filter = ('status', 'language', 'level', 'start_time')
    search_fields = ('instructor__user__username', 'student__username')
    date_hierarchy = 'start_time'
    
    fieldsets = (
        ('Session Information', {
            'fields': ('instructor', 'student', 'start_time', 'end_time', 'duration_minutes')
        }),
        ('Language Details', {
            'fields': ('language', 'level')
        }),
        ('Status', {
            'fields': ('status', 'meeting')
        }),
    )
    
    actions = ['mark_as_completed', 'mark_as_cancelled']
    
    def mark_as_completed(self, request, queryset):
        queryset.update(status='completed')
    mark_as_completed.short_description = "Mark selected sessions as completed"
    
    def mark_as_cancelled(self, request, queryset):
        queryset.update(status='cancelled')
    mark_as_cancelled.short_description = "Mark selected sessions as cancelled"

@admin.register(GroupSession)
class GroupSessionAdmin(admin.ModelAdmin):
    list_display = ('title', 'instructor', 'language', 'level', 'start_time', 'max_students', 'enrollment_percentage', 'status')
    list_filter = ('status', 'language', 'level', 'start_time')
    search_fields = ('title', 'instructor__user__username', 'description')
    date_hierarchy = 'start_time'
    filter_horizontal = ('students',)
    
    fieldsets = (
        ('Session Information', {
            'fields': ('title', 'instructor', 'description', 'start_time', 'end_time', 'duration_minutes')
        }),
        ('Language Details', {
            'fields': ('language', 'level')
        }),
        ('Enrollment', {
            'fields': ('max_students', 'students', 'price')
        }),
        ('Status', {
            'fields': ('status', 'meeting')
        }),
    )
    
    actions = ['mark_as_completed', 'mark_as_cancelled']
    
    def mark_as_completed(self, request, queryset):
        queryset.update(status='completed')
    mark_as_completed.short_description = "Mark selected sessions as completed"
    
    def mark_as_cancelled(self, request, queryset):
        queryset.update(status='cancelled')
    mark_as_cancelled.short_description = "Mark selected sessions as cancelled"

@admin.register(InstructorReview)
class InstructorReviewAdmin(admin.ModelAdmin):
    list_display = ('instructor', 'student', 'rating', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('instructor__user__username', 'student__username', 'comment')
    readonly_fields = ('created_at',)

@admin.register(CreditTransaction)
class CreditTransactionAdmin(admin.ModelAdmin):
    list_display = ('student', 'amount', 'transaction_type', 'created_at')
    list_filter = ('transaction_type', 'created_at')
    search_fields = ('student__username', 'description')
    readonly_fields = ('created_at',)
    
    fieldsets = (
        ('Transaction Details', {
            'fields': ('student', 'amount', 'transaction_type', 'description', 'created_at')
        }),
        ('Related Sessions', {
            'fields': ('private_session', 'group_session')
        }),
    )
    
    actions = ['export_transactions']
    
    def export_transactions(self, request, queryset):
        # This would be implemented to export transaction data
        self.message_user(request, "Selected transactions were exported")
    export_transactions.short_description = "Export selected transactions"