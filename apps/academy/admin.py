from django.contrib import admin
from .models import Course, Lesson, UserProgress, Resource, Assessment

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('title', 'instructor', 'category', 'rating', 'duration')
    list_filter = ('category', 'instructor')
    search_fields = ('title', 'description')

@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'duration', 'order')
    list_filter = ('course',)
    search_fields = ('title', 'content')

@admin.register(UserProgress)
class UserProgressAdmin(admin.ModelAdmin):
    list_display = ('user', 'course', 'last_accessed', 'progress_percentage')
    list_filter = ('user', 'course')

@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ('title', 'course')
    list_filter = ('course',)
    search_fields = ('title', 'description')

@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    list_display = ('title', 'course')
    list_filter = ('course',)
    search_fields = ('title', 'description')