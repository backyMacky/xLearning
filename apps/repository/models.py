from django.db import models
from django.conf import settings
from apps.content.models import Course, Lesson


class StudentFile(models.Model):
    """Model for files uploaded and managed by students"""
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='student_files')
    file = models.FileField(upload_to='student_files/')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    file_type = models.CharField(max_length=50)  # document, image, video, etc.
    
    # Optional associations
    course = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True, blank=True, related_name='student_files')
    lesson = models.ForeignKey(Lesson, on_delete=models.SET_NULL, null=True, blank=True, related_name='student_files')
    
    # Tracking data
    upload_date = models.DateTimeField(auto_now_add=True)
    last_accessed = models.DateTimeField(auto_now=True)
    view_count = models.IntegerField(default=0)
    
    def __str__(self):
        return f"{self.title} - {self.student.username}"
    
    def increment_view_count(self):
        """Increment the view count when file is accessed"""
        self.view_count += 1
        self.save(update_fields=['view_count', 'last_accessed'])
    
    class Meta:
        app_label = 'repository'


class TeacherResource(models.Model):
    """Model for resources shared by teachers with students"""
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='teacher_resources')
    file = models.FileField(upload_to='teacher_resources/')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    
    # Sharing options
    is_public = models.BooleanField(default=False)
    shared_with = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='accessible_resources', blank=True)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, null=True, blank=True, related_name='course_resources')
    
    # Tracking data
    upload_date = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.title} - {self.teacher.username}"
    
    class Meta:
        app_label = 'repository'


class ResourceAccess(models.Model):
    """Model to track student access to resources"""
    resource = models.ForeignKey(TeacherResource, on_delete=models.CASCADE, related_name='access_logs')
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='resource_access_logs')
    access_time = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name_plural = "Resource Accesses"
        ordering = ['-access_time']
        app_label = 'repository'
    
    def __str__(self):
        return f"{self.student.username} accessed {self.resource.title} at {self.access_time}"


class ResourceCollection(models.Model):
    """Model for organizing resources into collections"""
    name = models.CharField(max_length=255)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='resource_collections')
    resources = models.ManyToManyField(TeacherResource, related_name='collections', blank=True)
    student_files = models.ManyToManyField(StudentFile, related_name='collections', blank=True)
    
    # For organizing collections hierarchically
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='subcollections')
    
    def __str__(self):
        return f"{self.name} ({self.owner.username})"
    
    class Meta:
        app_label = 'repository'