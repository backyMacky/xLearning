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



class SessionStatus(models.Model):
    """Model for tracking different session statuses"""
    CATEGORY_CHOICES = [
        ('live', 'Live Status'),
        ('end', 'End Status'),
        ('system', 'System Status'),
    ]
    
    name = models.CharField(max_length=50)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True, null=True)
    color = models.CharField(max_length=20, help_text="CSS color class, e.g. 'primary', 'success'", default="primary")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='live')
    order = models.PositiveSmallIntegerField(default=0)
    
    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ['category', 'order']
        verbose_name_plural = "Session Statuses"


class BaseSession(models.Model):
    """Abstract base model with common fields for both private and group sessions"""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('no-show', 'No Show'),
    ]
    
    instructor = models.ForeignKey('booking.Instructor', on_delete=models.CASCADE, related_name='%(class)s_sessions')
    language = models.ForeignKey('content.Language', on_delete=models.PROTECT, related_name='%(class)s_sessions')
    level = models.ForeignKey('content.LanguageLevel', on_delete=models.PROTECT, related_name='%(class)s_sessions')
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    duration_minutes = models.PositiveIntegerField(default=60)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    status_detail = models.ForeignKey(SessionStatus, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_sessions')
    
    # Dates for tracking lifecycle
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Fields for tracking status changes
    cancellation_reason = models.TextField(blank=True, null=True)
    cancellation_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_cancellations')
    completion_notes = models.TextField(blank=True, null=True)
    
    # Integration fields
    meeting_link = models.URLField(blank=True, null=True)
    recording_url = models.URLField(blank=True, null=True)
    
    @property
    def is_cancelled(self):
        return self.status == 'cancelled'
    
    @property
    def is_completed(self):
        return self.status == 'completed'
    
    @property
    def is_active(self):
        """Session is currently happening"""
        now = timezone.now()
        return (
            self.status in ['scheduled', 'active'] and 
            self.start_time <= now and 
            self.end_time >= now
        )
    
    @property
    def is_upcoming(self):
        """Session is in the future"""
        now = timezone.now()
        return self.status == 'scheduled' and self.start_time > now
    
    @property
    def is_past(self):
        """Session has ended"""
        now = timezone.now()
        return self.end_time < now
    
    @property
    def duration_display(self):
        """Return a human-readable duration"""
        hours = self.duration_minutes // 60
        minutes = self.duration_minutes % 60
        
        if hours == 0:
            return f"{minutes} minute{'s' if minutes != 1 else ''}"
        elif minutes == 0:
            return f"{hours} hour{'s' if hours != 1 else ''}"
        else:
            return f"{hours} hour{'s' if hours != 1 else ''} {minutes} minute{'s' if minutes != 1 else ''}"
    
    def mark_as_published(self):
        """Publish the session"""
        if self.status == 'draft':
            self.status = 'scheduled'
            self.published_at = timezone.now()
            self.save(update_fields=['status', 'published_at'])
    
    def mark_as_cancelled(self, reason=None, cancelled_by=None):
        """Cancel the session"""
        if self.status in ['draft', 'scheduled', 'active']:
            self.status = 'cancelled'
            self.cancelled_at = timezone.now()
            self.cancellation_reason = reason
            self.cancellation_by = cancelled_by
            self.save(update_fields=['status', 'cancelled_at', 'cancellation_reason', 'cancellation_by'])
    
    def mark_as_completed(self, notes=None):
        """Mark the session as completed"""
        if self.status in ['scheduled', 'active']:
            self.status = 'completed'
            self.completed_at = timezone.now()
            self.completion_notes = notes
            self.save(update_fields=['status', 'completed_at', 'completion_notes'])
    
    def mark_as_no_show(self):
        """Mark session as no-show when student(s) don't attend"""
        if self.status in ['scheduled', 'active']:
            self.status = 'no-show'
            self.cancelled_at = timezone.now()
            self.save(update_fields=['status', 'cancelled_at'])
    
    class Meta:
        abstract = True


class PrivateSession(BaseSession):
    """Model for private 1-on-1 sessions"""
    
    # Fields unique to private sessions
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='private_sessions', null=True, blank=True)
    is_trial = models.BooleanField(default=False)
    
    # Override from base class to support compatibility with existing code
    status = models.CharField(max_length=20, choices=BaseSession.STATUS_CHOICES + [('available', 'Available'), ('booked', 'Booked')], default='draft')
    
    @property
    def is_private(self):
        return True
    
    @property
    def is_available(self):
        """Session is available for booking"""
        return self.status == 'available' and self.is_upcoming
    
    @property
    def is_booked(self):
        """Session is booked by a student"""
        return self.status == 'booked' and self.student is not None
    
    def __str__(self):
        student_name = self.student.username if self.student else "No student"
        return f"Private: {self.instructor.user.username} with {student_name} on {self.start_time.strftime('%Y-%m-%d %H:%M')}"


class GroupSession(BaseSession):
    """Model for group sessions with multiple students"""
    
    # Fields unique to group sessions
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    max_students = models.PositiveIntegerField(null=True, blank=True)
    min_students = models.PositiveIntegerField(default=2)
    students = models.ManyToManyField(User, related_name='group_sessions', blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    tags = models.CharField(max_length=255, blank=True, null=True, help_text="Comma-separated tags")
    
    @property
    def is_private(self):
        return False
    
    @property
    def is_full(self):
        """Check if session has reached max capacity"""
        if not self.max_students:
            return False
        return self.students.count() >= self.max_students
    
    @property
    def enrollment_percentage(self):
        """Calculate percentage of filled slots"""
        if not self.max_students or self.max_students == 0:
            return 0
        return min(100, int((self.students.count() / self.max_students) * 100))
    
    @property
    def can_run(self):
        """Check if session has minimum required participants"""
        return self.students.count() >= self.min_students
    
    @property
    def slots_available(self):
        """Number of available slots remaining"""
        if not self.max_students:
            return None
        return max(0, self.max_students - self.students.count())
    
    def __str__(self):
        return f"Group: {self.title} by {self.instructor.user.username} on {self.start_time.strftime('%Y-%m-%d %H:%M')}"


class SessionFeedback(models.Model):
    """Model for tracking session feedback from both students and instructors"""
    RATING_CHOICES = [
        (1, '1 - Poor'),
        (2, '2 - Below Average'),
        (3, '3 - Average'),
        (4, '4 - Good'),
        (5, '5 - Excellent'),
    ]
    
    SESSION_TYPE_CHOICES = [
        ('private', 'Private Session'),
        ('group', 'Group Session'),
    ]
    
    # Basic information
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='given_session_feedback')
    session_type = models.CharField(max_length=10, choices=SESSION_TYPE_CHOICES)
    private_session = models.ForeignKey(PrivateSession, on_delete=models.CASCADE, null=True, blank=True, related_name='feedback')
    group_session = models.ForeignKey(GroupSession, on_delete=models.CASCADE, null=True, blank=True, related_name='feedback')
    
    # Feedback details
    rating = models.PositiveSmallIntegerField(choices=RATING_CHOICES)
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Specific feedback aspects (optional)
    teaching_quality = models.PositiveSmallIntegerField(choices=RATING_CHOICES, null=True, blank=True)
    technical_quality = models.PositiveSmallIntegerField(choices=RATING_CHOICES, null=True, blank=True)
    content_relevance = models.PositiveSmallIntegerField(choices=RATING_CHOICES, null=True, blank=True)
    
    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(private_session__isnull=False) | models.Q(group_session__isnull=False),
                name='feedback_has_session'
            ),
            models.UniqueConstraint(
                fields=['user', 'private_session'],
                name='unique_private_session_feedback',
                condition=models.Q(private_session__isnull=False)
            ),
            models.UniqueConstraint(
                fields=['user', 'group_session'],
                name='unique_group_session_feedback',
                condition=models.Q(group_session__isnull=False)
            ),
        ]
    
    def __str__(self):
        session_info = ""
        if self.private_session:
            instructor = self.private_session.instructor.user.username
            date = self.private_session.start_time.strftime("%Y-%m-%d")
            session_info = f"Private session with {instructor} on {date}"
        elif self.group_session:
            session_info = f"Group session: {self.group_session.title}"
            
        return f"Feedback by {self.user.username} for {session_info} - {self.rating}/5"


class SessionReport(models.Model):
    """Model for instructor reports on sessions"""
    SESSION_TYPE_CHOICES = [
        ('private', 'Private Session'),
        ('group', 'Group Session'),
    ]
    
    PROGRESS_CHOICES = [
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('satisfactory', 'Satisfactory'),
        ('needs_improvement', 'Needs Improvement'),
        ('poor', 'Poor'),
    ]
    
    # Session information
    instructor = models.ForeignKey('booking.Instructor', on_delete=models.CASCADE, related_name='session_reports')
    session_type = models.CharField(max_length=10, choices=SESSION_TYPE_CHOICES)
    private_session = models.OneToOneField(PrivateSession, on_delete=models.CASCADE, null=True, blank=True, related_name='report')
    group_session = models.OneToOneField(GroupSession, on_delete=models.CASCADE, null=True, blank=True, related_name='report')
    
    # Report details
    summary = models.TextField()
    topics_covered = models.TextField()
    student_progress = models.CharField(max_length=20, choices=PROGRESS_CHOICES, default='satisfactory')
    recommendations = models.TextField(blank=True, null=True)
    materials_used = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # For private sessions only
    student_strengths = models.TextField(blank=True, null=True)
    student_weaknesses = models.TextField(blank=True, null=True)
    
    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(private_session__isnull=False) | models.Q(group_session__isnull=False),
                name='report_has_session'
            ),
        ]
    
    def __str__(self):
        if self.private_session:
            student = self.private_session.student.username if self.private_session.student else "No student"
            date = self.private_session.start_time.strftime("%Y-%m-%d")
            return f"Report for private session with {student} on {date}"
        elif self.group_session:
            return f"Report for group session: {self.group_session.title}"
        return "Session Report"


class SessionAttendance(models.Model):
    """Model for tracking attendance in group sessions"""
    session = models.ForeignKey(GroupSession, on_delete=models.CASCADE, related_name='attendance')
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='session_attendance')
    attended = models.BooleanField(default=False)
    join_time = models.DateTimeField(null=True, blank=True)
    leave_time = models.DateTimeField(null=True, blank=True)
    attendance_duration = models.PositiveIntegerField(help_text="Duration in minutes", null=True, blank=True)
    notes = models.TextField(blank=True, null=True)
    
    class Meta:
        unique_together = ['session', 'student']
    
    def __str__(self):
        attendance_status = "Attended" if self.attended else "Absent"
        return f"{self.student.username} - {attendance_status} - {self.session}"
    
    def mark_attended(self, join_time=None):
        """Mark student as attended"""
        self.attended = True
        if join_time:
            self.join_time = join_time
        else:
            self.join_time = timezone.now()
        self.save(update_fields=['attended', 'join_time'])
    
    def mark_left(self, leave_time=None):
        """Record when student left the session"""
        if leave_time:
            self.leave_time = leave_time
        else:
            self.leave_time = timezone.now()
            
        # Calculate duration if both join and leave times are set
        if self.join_time and self.leave_time:
            duration = (self.leave_time - self.join_time).total_seconds() / 60
            self.attendance_duration = round(duration)
            
        self.save(update_fields=['leave_time', 'attendance_duration'])
