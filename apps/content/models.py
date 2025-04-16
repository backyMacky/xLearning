from django.utils import timezone
from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify
from django.urls import reverse


class Language(models.Model):
    """Model for languages offered on the platform"""
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10)  # ISO language code (e.g., 'en', 'fr', 'sw')
    is_active = models.BooleanField(default=True)
    flag_icon = models.CharField(max_length=50, blank=True, null=True)  # CSS class for flag icon
    
    def __str__(self):
        return self.name
    
    class Meta:
        app_label = 'content'
        ordering = ['name']


class LanguageLevel(models.Model):
    """Model for language proficiency levels"""
    LEVEL_CHOICES = [
        ('A1', 'Beginner'),
        ('A2', 'Elementary'),
        ('B1', 'Intermediate'),
        ('B2', 'Upper Intermediate'),
        ('C1', 'Advanced'),
        ('C2', 'Proficient'),
    ]
    
    code = models.CharField(max_length=2, choices=LEVEL_CHOICES)
    name = models.CharField(max_length=50)
    description = models.TextField()
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    
    class Meta:
        app_label = 'content'
        ordering = ['code']


class Course(models.Model):
    """Model for language learning courses"""
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    description = models.TextField()
    language = models.ForeignKey(Language, on_delete=models.CASCADE, related_name='courses', null=True)
    level = models.ForeignKey(LanguageLevel, on_delete=models.CASCADE, related_name='courses', null=True)
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='taught_courses')
    students = models.ManyToManyField(User, related_name='enrolled_courses', blank=True)
    image = models.ImageField(upload_to='course_images/', blank=True, null=True)
    is_featured = models.BooleanField(default=False)
    is_published = models.BooleanField(default=False)
    duration_weeks = models.PositiveIntegerField(default=8)  # Typical course duration in weeks
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.title} ({self.language.name} - {self.level.code})"
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)
    
    def get_absolute_url(self):
        return reverse('content:course_detail', kwargs={'slug': self.slug})
    
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
        ordering = ['-created_at']


class LearningModule(models.Model):
    """Model for organizing lessons into modules/units"""
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='modules')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    order = models.PositiveIntegerField(default=0)
    
    def __str__(self):
        return f"{self.course.title} - {self.title}"
    
    class Meta:
        app_label = 'content'
        ordering = ['course', 'order']


class Lesson(models.Model):
    """Model for lessons within modules"""
    module = models.ForeignKey(LearningModule, on_delete=models.CASCADE, related_name='lessons', null=True)
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, blank=True)
    content = models.TextField()
    video_url = models.CharField(max_length=255, blank=True, null=True)
    audio_url = models.CharField(max_length=255, blank=True, null=True)
    attachment = models.FileField(upload_to='lesson_attachments/', blank=True, null=True)
    duration_minutes = models.PositiveIntegerField(default=30)  # Estimated time to complete
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)  # Changed from auto_now_add=True
    updated_at = models.DateTimeField(auto_now=True)  # Left auto_now=True
    
    @property
    def course(self):
        return self.module.course
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)
    
    def get_absolute_url(self):
        return reverse('content:lesson_detail', kwargs={
            'course_slug': self.module.course.slug,
            'lesson_slug': self.slug
        })
    
    def get_next_lesson(self):
        """Get the next lesson in the course sequence"""
        # First try to get next lesson in the same module
        next_lessons = Lesson.objects.filter(
            module=self.module,
            order__gt=self.order
        ).order_by('order')
        
        if next_lessons.exists():
            return next_lessons.first()
        
        # Try to get the first lesson of the next module
        next_modules = LearningModule.objects.filter(
            course=self.module.course,
            order__gt=self.module.order
        ).order_by('order')
        
        if next_modules.exists():
            next_module = next_modules.first()
            first_lesson = next_module.lessons.order_by('order').first()
            if first_lesson:
                return first_lesson
        
        return None
    
    class Meta:
        ordering = ['module', 'order']
        app_label = 'content'
        unique_together = ['module', 'slug']

class LessonCompletion(models.Model):
    """Model to track which lessons a student has completed"""
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='completed_lessons')
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='completions')
    completed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        app_label = 'content'
        unique_together = ['student', 'lesson']


class CourseProgress(models.Model):
    """Model to track a student's progress in a course"""
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='course_progress')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='student_progress')
    last_accessed = models.DateTimeField(auto_now=True)
    
    @property
    def lessons_completed(self):
        """Get all lessons completed by this student for this course"""
        return Lesson.objects.filter(
            completions__student=self.student,
            module__course=self.course
        )
    
    @property
    def progress_percentage(self):
        total_lessons = Lesson.objects.filter(module__course=self.course).count()
        if total_lessons == 0:
            return 0
        completed_count = self.lessons_completed.count()
        return (completed_count / total_lessons) * 100
    
    class Meta:
        app_label = 'content'
        unique_together = ['student', 'course']

class Resource(models.Model):
    """Model for educational resources shared with students"""
    RESOURCE_TYPES = [
        ('document', 'Document'),
        ('video', 'Video'),
        ('audio', 'Audio'),
        ('image', 'Image'),
        ('link', 'External Link'),
        ('exercise', 'Exercise'),
        ('vocabulary', 'Vocabulary List'),
    ]
    
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    resource_type = models.CharField(max_length=20, choices=RESOURCE_TYPES, default='document')
    file = models.FileField(upload_to='language_resources/', blank=True, null=True)
    external_url = models.URLField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_resources')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='resources', null=True, blank=True)
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='resources', null=True, blank=True)
    language = models.ForeignKey(Language, on_delete=models.CASCADE, related_name='resources')
    level = models.ForeignKey(LanguageLevel, on_delete=models.CASCADE, related_name='resources')
    is_public = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.title
    
    class Meta:
        app_label = 'content'
        ordering = ['-created_at']