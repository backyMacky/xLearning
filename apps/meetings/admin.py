from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import Meeting


@admin.register(Meeting)
class MeetingAdmin(admin.ModelAdmin):
    list_display = ('title', 'teacher_name', 'formatted_start_time', 'duration', 'status', 'student_count', 'meeting_link_display')
    list_filter = ('status', 'start_time', 'created_at', 'teacher')
    search_fields = ('title', 'teacher__username', 'teacher__email', 'meeting_code', 'notes')
    readonly_fields = ('id', 'created_at', 'updated_at', 'meeting_code', 'google_calendar_link')
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'title', 'teacher', 'students', 'notes')
        }),
        ('Scheduling', {
            'fields': ('start_time', 'duration', 'status')
        }),
        ('Meeting Details', {
            'fields': ('meeting_code', 'meeting_link', 'recording_url')
        }),
        ('System Information', {
            'fields': ('created_at', 'updated_at', 'google_calendar_link'),
            'classes': ('collapse',)
        }),
    )
    filter_horizontal = ('students',)
    actions = ['mark_as_completed', 'mark_as_cancelled', 'send_reminder_emails']
    date_hierarchy = 'start_time'

    def teacher_name(self, obj):
        return obj.teacher.get_full_name() or obj.teacher.username
    teacher_name.short_description = 'Teacher'
    teacher_name.admin_order_field = 'teacher__username'

    def formatted_start_time(self, obj):
        return obj.start_time.strftime('%Y-%m-%d %H:%M')
    formatted_start_time.short_description = 'Start Time'
    formatted_start_time.admin_order_field = 'start_time'

    def student_count(self, obj):
        count = obj.students.count()
        url = reverse('admin:auth_user_changelist') + f'?id__in={",".join(str(s.id) for s in obj.students.all())}'
        return format_html('<a href="{}">{} students</a>', url, count)
    student_count.short_description = 'Students'

    def meeting_link_display(self, obj):
        if obj.meeting_link:
            return format_html('<a href="{}" target="_blank">Join Meeting</a>', obj.meeting_link)
        return '-'
    meeting_link_display.short_description = 'Meeting Link'

    def mark_as_completed(self, request, queryset):
        updated = 0
        for meeting in queryset:
            if meeting.status != 'completed':
                meeting.status = 'completed'
                meeting.save(update_fields=['status'])
                updated += 1
        self.message_user(request, f"{updated} meetings marked as completed.")
    mark_as_completed.short_description = "Mark selected meetings as completed"

    def mark_as_cancelled(self, request, queryset):
        updated = 0
        for meeting in queryset:
            if meeting.status not in ['completed', 'cancelled']:
                success, _ = meeting.cancel(notify_participants=False)
                if success:
                    updated += 1
        self.message_user(request, f"{updated} meetings marked as cancelled.")
    mark_as_cancelled.short_description = "Mark selected meetings as cancelled"

    def send_reminder_emails(self, request, queryset):
        sent_count = 0
        for meeting in queryset:
            if meeting.status == 'scheduled':
                sent_count += meeting.send_reminders()
        self.message_user(request, f"Sent {sent_count} reminder emails for selected meetings.")
    send_reminder_emails.short_description = "Send reminder emails for selected meetings"

    def get_queryset(self, request):
        """Optimize queries by prefetching related objects"""
        return super().get_queryset(request).prefetch_related('students').select_related('teacher')