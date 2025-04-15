from django.db import models
from django.contrib.auth.models import User


class Course(models.Model):
    """Model for educational courses"""
    title = models.CharField(max_length=255)
    description = models.TextField()
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='taught_courses')
    students = models.ManyToManyField(User, related_name='enrolled_courses', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.title
    
    def add_student(self, student):
        """Add a student to the course"""
        if student not in self.students.all():
            self.students.add(student)
            return True
        return False
    
    def remove_student(self, student):
        """Remove a student from the course"""
        if student in self.students.all():
            self.students.remove(student)
            return True
        return False
    
    class Meta:
        app_label = 'content'


class Lesson(models.Model):
    """Model for lessons within courses"""
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='lessons')
    title = models.CharField(max_length=255)
    content = models.TextField()
    video_url = models.CharField(max_length=255, blank=True, null=True)
    attachment = models.FileField(upload_to='lesson_attachments/', blank=True, null=True)
    order = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['order']
        app_label = 'content'
    
    def __str__(self):
        return f"{self.course.title} - {self.title}"
    
    def get_next_lesson(self):
        """Get the next lesson in the course sequence"""
        next_lessons = Lesson.objects.filter(
            course=self.course,
            order__gt=self.order
        ).order_by('order')
        
        if next_lessons.exists():
            return next_lessons.first()
        return None


class Resource(models.Model):
    """Model for educational resources shared with students"""
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='resources/')
    type = models.CharField(max_length=50)  # document, video, audio, etc.
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_resources')
    assigned_to = models.ManyToManyField(User, related_name='assigned_resources', blank=True)
    
    def __str__(self):
        return self.title
    
    def share(self, users):
        """Share resource with specific users"""
        if not isinstance(users, (list, tuple)):
            users = [users]
            
        for user in users:
            self.assigned_to.add(user)
    
    class Meta:
        app_label = 'content'