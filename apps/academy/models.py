from django.db import models
from django.contrib.auth.models import User

class Course(models.Model):
    """Model for courses in the academy platform"""
    title = models.CharField(max_length=255)
    description = models.TextField()
    image = models.ImageField(upload_to='course_images/', null=True, blank=True)
    instructor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='courses_taught')
    students = models.ManyToManyField(User, related_name='courses_enrolled', blank=True)
    duration = models.IntegerField(help_text="Duration in minutes")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Course categories based on the JSON menu
    CATEGORY_CHOICES = [
        ('UI/UX', 'UI/UX'),
        ('Web', 'Web'),
        ('SEO', 'SEO'),
        ('Music', 'Music'),
        ('Painting', 'Painting'),
    ]
    
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    rating = models.DecimalField(max_digits=3, decimal_places=1, default=0.0)
    
    def __str__(self):
        return self.title

class Lesson(models.Model):
    """Model for lessons within courses"""
    title = models.CharField(max_length=255)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='lessons')
    content = models.TextField()
    duration = models.IntegerField(help_text="Duration in minutes")
    order = models.IntegerField(default=0)
    
    def __str__(self):
        return f"{self.course.title} - {self.title}"

class UserProgress(models.Model):
    """Model to track user progress through courses"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='course_progress')
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    lessons_completed = models.ManyToManyField(Lesson, blank=True)
    last_accessed = models.DateTimeField(auto_now=True)
    
    @property
    def progress_percentage(self):
        total_lessons = self.course.lessons.count()
        if total_lessons == 0:
            return 0
        completed_lessons = self.lessons_completed.count()
        return (completed_lessons / total_lessons) * 100
    
    def __str__(self):
        return f"{self.user.username}'s progress on {self.course.title}"

class Resource(models.Model):
    """Model for educational resources"""
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    file = models.FileField(upload_to='resources/')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='resources')
    
    def __str__(self):
        return self.title
        
class Assessment(models.Model):
    """Model for course assessments"""
    title = models.CharField(max_length=255)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='assessments')
    description = models.TextField()
    
    def __str__(self):
        return f"{self.course.title} - {self.title}"