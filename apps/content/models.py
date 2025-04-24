from django.utils import timezone
from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify
from django.urls import reverse
from multiselectfield import MultiSelectField
from django.db.models.signals import post_save
from django.dispatch import receiver

class Course(models.Model):
    """Model for language learning courses"""
    LANGUAGE_CHOICES = [
        ('en', 'English'),
        ('fr', 'French'),
        ('es', 'Spanish'),
        ('de', 'German'),
        ('it', 'Italian'),
        ('pt', 'Portuguese'),
        ('ru', 'Russian'),
        ('zh', 'Chinese'),
        ('ja', 'Japanese'),
        ('ko', 'Korean'),
        ('ar', 'Arabic'),
        ('hi', 'Hindi'),
        ('sw', 'Swahili'),
    ]
    
    LEVEL_CHOICES = [
        ('A1', 'Beginner'),
        ('A2', 'Elementary'),
        ('B1', 'Intermediate'),
        ('B2', 'Upper Intermediate'),
        ('C1', 'Advanced'),
        ('C2', 'Proficient'),
    ]
    
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    description = models.TextField()
    language = models.CharField(max_length=10, choices=LANGUAGE_CHOICES)
    level = models.CharField(max_length=2, choices=LEVEL_CHOICES)
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='taught_courses')
    students = models.ManyToManyField(User, related_name='enrolled_courses', blank=True)
    image = models.ImageField(upload_to='course_images/', blank=True, null=True)
    is_featured = models.BooleanField(default=False)
    is_published = models.BooleanField(default=False)
    duration_weeks = models.PositiveIntegerField(default=8)  # Typical course duration in weeks
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.title} ({self.get_language_display()} - {self.level})"
    
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
        ordering = ['course', 'order']


class Lesson(models.Model):
    """Model for lessons within modules"""
    module = models.ForeignKey(LearningModule, on_delete=models.CASCADE, related_name='lessons')
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, blank=True)
    content = models.TextField()
    video_url = models.CharField(max_length=255, blank=True, null=True)
    audio_url = models.CharField(max_length=255, blank=True, null=True)
    attachment = models.FileField(upload_to='lesson_attachments/', blank=True, null=True)
    duration_minutes = models.PositiveIntegerField(default=30)  # Estimated time to complete
    tags = models.CharField(max_length=255, blank=True, help_text="Comma-separated tags")
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
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
    
    def generate_keywords(self):
        """Automatically generate keywords based on lesson content"""
        from collections import Counter
        import re
        
        # Remove HTML tags if present
        from django.utils.html import strip_tags
        cleaned_content = strip_tags(self.content)
        
        # Extract words from content
        words = re.findall(r'\b\w{3,}\b', cleaned_content.lower())
        
        # Common words to exclude
        stop_words = {'the', 'and', 'this', 'that', 'with', 'from', 'have', 'for', 'not', 'are', 'was', 'were', 'been'}
        
        # Filter out common words
        filtered_words = [word for word in words if word not in stop_words]
        
        # Count occurrences
        word_counts = Counter(filtered_words)
        
        # Get top 10 words as keywords
        common_words = [word for word, count in word_counts.most_common(10)]
        
        # Update tags
        self.tags = ", ".join(common_words)
        self.save(update_fields=['tags'])
    
    class Meta:
        ordering = ['module', 'order']
        unique_together = ['module', 'slug']


class LessonCompletion(models.Model):
    """Model to track which lessons a student has completed"""
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='completed_lessons')
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='completions')
    completed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
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
    file = models.FileField(upload_to='content_resources/', blank=True, null=True)
    external_url = models.URLField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_resources')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='resources', null=True, blank=True)
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='resources', null=True, blank=True)
    language = models.CharField(max_length=10, choices=Course.LANGUAGE_CHOICES)
    level = models.CharField(max_length=2, choices=Course.LEVEL_CHOICES)
    tags = models.CharField(max_length=255, blank=True, help_text="Comma-separated tags")
    is_public = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.title
    
    class Meta:
        ordering = ['-created_at']


class Instructor(models.Model):
    """Model for language instructors"""
    SPECIALTY_CHOICES = [
        ('business', 'Business Language'),
        ('academic', 'Academic Language'),
        ('conversation', 'Conversation Practice'),
        ('exam', 'Exam Preparation'),
        ('children', 'Teaching Children'),
        ('medical', 'Medical Terminology'),
        ('travel', 'Travel & Tourism'),
        ('technical', 'Technical & Scientific'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='instructor_profile')
    bio = models.TextField(blank=True, null=True)
    teaching_style = models.TextField(blank=True, null=True)
    profile_image = models.ImageField(upload_to='instructor_profiles/', blank=True, null=True)
    is_available = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    hourly_rate = models.DecimalField(max_digits=6, decimal_places=2, default=25.00)
    
    # Using MultiSelectField for multiple selections
    teaching_languages = MultiSelectField(choices=Course.LANGUAGE_CHOICES, max_length=100, blank=True)
    specialties = MultiSelectField(choices=SPECIALTY_CHOICES, max_length=100, blank=True)
    
    # Dates
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Instructor: {self.user.username}"
    
    @property
    def rating(self):
        """Calculate average rating from reviews"""
        from django.db.models import Avg
        reviews = InstructorReview.objects.filter(instructor=self)
        if reviews.exists():
            return reviews.aggregate(Avg('rating'))['rating__avg']
        return 0
    
    @property
    def review_count(self):
        """Count how many reviews this instructor has"""
        return InstructorReview.objects.filter(instructor=self).count()
    
    @property
    def sessions_completed(self):
        """Count completed sessions"""
        return 0  # Placeholder - to be implemented based on session models


class InstructorReview(models.Model):
    """Model for student reviews of instructors"""
    instructor = models.ForeignKey(Instructor, on_delete=models.CASCADE, related_name='reviews')
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='given_reviews')
    rating = models.PositiveSmallIntegerField(choices=[(i, i) for i in range(1, 6)])
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Review by {self.student.username} for {self.instructor.user.username}"
    
    class Meta:
        unique_together = ['instructor', 'student']
        ordering = ['-created_at']


class PrivateSession(models.Model):
    """Model for private 1-on-1 sessions"""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('available', 'Available'),
        ('booked', 'Booked'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('no-show', 'No Show'),
    ]
    
    LANGUAGE_CHOICES = [
        ('en', 'English'),
        ('fr', 'French'),
        ('es', 'Spanish'),
        ('de', 'German'),
        ('it', 'Italian'),
        ('pt', 'Portuguese'),
        ('ru', 'Russian'),
        ('zh', 'Chinese'),
        ('ja', 'Japanese'),
        ('ko', 'Korean'),
        ('ar', 'Arabic'),
        ('hi', 'Hindi'),
        ('sw', 'Swahili'),
    ]
    
    LEVEL_CHOICES = [
        ('A1', 'Beginner'),
        ('A2', 'Elementary'),
        ('B1', 'Intermediate'),
        ('B2', 'Upper Intermediate'),
        ('C1', 'Advanced'),
        ('C2', 'Proficient'),
    ]
    
    instructor = models.ForeignKey('Instructor', on_delete=models.CASCADE, related_name='private_sessions')
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='private_sessions', null=True, blank=True)
    language = models.CharField(max_length=10, choices=LANGUAGE_CHOICES)
    level = models.CharField(max_length=2, choices=LEVEL_CHOICES)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    duration_minutes = models.PositiveIntegerField(default=60)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    is_trial = models.BooleanField(default=False)
    
    # Meeting info
    meeting_link = models.URLField(blank=True, null=True)
    recording_url = models.URLField(blank=True, null=True)
    
    # Dates for tracking lifecycle
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        student_name = self.student.username if self.student else "No student"
        return f"Private: {self.instructor.user.username} with {student_name} on {self.start_time.strftime('%Y-%m-%d %H:%M')}"
    
    @property
    def is_booked(self):
        """Check if session is booked"""
        return self.status == 'booked' and self.student is not None
    
    @property
    def is_available(self):
        """Check if session is available for booking"""
        return self.status == 'available' and timezone.now() < self.start_time
    
    def mark_as_published(self):
        """Publish the session"""
        if self.status == 'draft':
            self.status = 'available'
            self.published_at = timezone.now()
            self.save(update_fields=['status', 'published_at'])
    
    def mark_as_booked(self, student):
        """Mark session as booked by a student"""
        if self.status == 'available':
            self.status = 'booked'
            self.student = student
            self.save(update_fields=['status', 'student'])
    
    def mark_as_cancelled(self, reason=None, cancelled_by=None):
        """Cancel the session"""
        if self.status in ['draft', 'available', 'booked', 'active']:
            self.status = 'cancelled'
            self.cancelled_at = timezone.now()
            self.save(update_fields=['status', 'cancelled_at'])
    
    def mark_as_completed(self):
        """Mark the session as completed"""
        if self.status in ['booked', 'active']:
            self.status = 'completed'
            self.completed_at = timezone.now()
            self.save(update_fields=['status', 'completed_at'])
    
    class Meta:
        ordering = ['-start_time']


class GroupSession(models.Model):
    """Model for group sessions with multiple students"""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    LANGUAGE_CHOICES = [
        ('en', 'English'),
        ('fr', 'French'),
        ('es', 'Spanish'),
        ('de', 'German'),
        ('it', 'Italian'),
        ('pt', 'Portuguese'),
        ('ru', 'Russian'),
        ('zh', 'Chinese'),
        ('ja', 'Japanese'),
        ('ko', 'Korean'),
        ('ar', 'Arabic'),
        ('hi', 'Hindi'),
        ('sw', 'Swahili'),
    ]
    
    LEVEL_CHOICES = [
        ('A1', 'Beginner'),
        ('A2', 'Elementary'),
        ('B1', 'Intermediate'),
        ('B2', 'Upper Intermediate'),
        ('C1', 'Advanced'),
        ('C2', 'Proficient'),
    ]
    
    instructor = models.ForeignKey('Instructor', on_delete=models.CASCADE, related_name='group_sessions')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    language = models.CharField(max_length=10, choices=LANGUAGE_CHOICES)
    level = models.CharField(max_length=2, choices=LEVEL_CHOICES)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    duration_minutes = models.PositiveIntegerField(default=60)
    max_students = models.PositiveIntegerField(default=5)
    min_students = models.PositiveIntegerField(default=2)
    students = models.ManyToManyField(User, related_name='group_sessions', blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    price = models.DecimalField(max_digits=6, decimal_places=2, default=15.00)
    tags = models.CharField(max_length=255, blank=True, help_text="Comma-separated tags")
    
    # Meeting info
    meeting_link = models.URLField(blank=True, null=True)
    recording_url = models.URLField(blank=True, null=True)
    
    # Dates for tracking lifecycle
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"Group: {self.title} by {self.instructor.user.username} on {self.start_time.strftime('%Y-%m-%d %H:%M')}"
    
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
    
    def mark_as_published(self):
        """Publish the session"""
        if self.status == 'draft':
            self.status = 'scheduled'
            self.published_at = timezone.now()
            self.save(update_fields=['status', 'published_at'])
    
    def mark_as_cancelled(self, reason=None):
        """Cancel the session"""
        if self.status in ['draft', 'scheduled', 'active']:
            self.status = 'cancelled'
            self.cancelled_at = timezone.now()
            self.save(update_fields=['status', 'cancelled_at'])
    
    def mark_as_completed(self):
        """Mark the session as completed"""
        if self.status in ['scheduled', 'active']:
            self.status = 'completed'
            self.completed_at = timezone.now()
            self.save(update_fields=['status', 'completed_at'])
    
    class Meta:
        ordering = ['-start_time']


class SessionFeedback(models.Model):
    """Model for tracking session feedback from students"""
    RATING_CHOICES = [(i, f"{i} Stars") for i in range(1, 6)]
    SESSION_TYPE_CHOICES = [
        ('private', 'Private Session'),
        ('group', 'Group Session'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='given_session_feedback')
    session_type = models.CharField(max_length=10, choices=SESSION_TYPE_CHOICES)
    private_session = models.ForeignKey(PrivateSession, on_delete=models.CASCADE, null=True, blank=True, related_name='feedback')
    group_session = models.ForeignKey(GroupSession, on_delete=models.CASCADE, null=True, blank=True, related_name='feedback')
    
    # Feedback details
    rating = models.PositiveSmallIntegerField(choices=RATING_CHOICES)
    comment = models.TextField()
    
    # Specific feedback aspects
    teaching_quality = models.PositiveSmallIntegerField(choices=RATING_CHOICES, null=True, blank=True)
    technical_quality = models.PositiveSmallIntegerField(choices=RATING_CHOICES, null=True, blank=True)
    content_relevance = models.PositiveSmallIntegerField(choices=RATING_CHOICES, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        session_info = ""
        if self.private_session:
            instructor = self.private_session.instructor.user.username
            date = self.private_session.start_time.strftime("%Y-%m-%d")
            session_info = f"Private session with {instructor} on {date}"
        elif self.group_session:
            session_info = f"Group session: {self.group_session.title}"
            
        return f"Feedback by {self.user.username} for {session_info} - {self.rating}/5"
    
    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(private_session__isnull=False) | models.Q(group_session__isnull=False),
                name='feedback_has_session'
            ),
        ]



# Flag to prevent recursive signal calls
_SYNCING_PRIVATE_SESSION = False
_SYNCING_GROUP_SESSION = False

@receiver(post_save, sender=PrivateSession)
def sync_private_session_to_booking(sender, instance, created, **kwargs):
    """Sync private session changes to booking app"""
    global _SYNCING_PRIVATE_SESSION
    
    # Prevent recursion
    if _SYNCING_PRIVATE_SESSION:
        return
    
    _SYNCING_PRIVATE_SESSION = True
    try:
        from apps.booking.models import PrivateSessionSlot, Instructor
        
        # If it's a new session, the creation is handled in the view
        if not created:
            # For existing sessions, find the corresponding booking slot
            try:
                booking_instructor = Instructor.objects.get(user=instance.instructor.user)
                
                # Find all matching slots
                booking_slots = PrivateSessionSlot.objects.filter(
                    instructor=booking_instructor,
                    start_time=instance.start_time
                )
                
                if booking_slots.exists():
                    # Update the first slot with new values
                    booking_slot = booking_slots.first()
                    
                    # Update the booking slot with new values
                    booking_slot.end_time = instance.end_time
                    booking_slot.duration_minutes = instance.duration_minutes
                    booking_slot.language = instance.language
                    booking_slot.level = instance.level
                    booking_slot.status = instance.status
                    
                    # Update student if booked
                    if instance.status == 'booked' and instance.student:
                        booking_slot.student = instance.student
                    
                    booking_slot.save()
                    
                    # Delete any duplicate slots beyond the first one
                    if booking_slots.count() > 1:
                        for slot in booking_slots[1:]:
                            slot.delete()
                else:
                    # Slot doesn't exist in booking app, create it
                    PrivateSessionSlot.objects.create(
                        instructor=booking_instructor,
                        start_time=instance.start_time,
                        end_time=instance.end_time,
                        duration_minutes=instance.duration_minutes,
                        language=instance.language,
                        level=instance.level,
                        status=instance.status,
                        student=instance.student if instance.status == 'booked' else None
                    )
            except Instructor.DoesNotExist:
                # Instructor doesn't exist in booking app
                pass
    except (ImportError, AttributeError):
        # Booking app not available or models not compatible
        pass
    finally:
        _SYNCING_PRIVATE_SESSION = False


@receiver(post_save, sender=GroupSession)
def sync_group_session_to_booking(sender, instance, created, **kwargs):
    """Sync group session changes to booking app"""
    global _SYNCING_GROUP_SESSION
    
    # Prevent recursion
    if _SYNCING_GROUP_SESSION:
        return
    
    _SYNCING_GROUP_SESSION = True
    try:
        from apps.booking.models import GroupSession as BookingGroupSession, Instructor
        
        # If it's a new session, the creation is handled in the view
        if not created:
            # For existing sessions, find the corresponding booking session
            try:
                booking_instructor = Instructor.objects.get(user=instance.instructor.user)
                
                # Find all matching sessions
                booking_sessions = BookingGroupSession.objects.filter(
                    instructor=booking_instructor,
                    start_time=instance.start_time,
                    title=instance.title
                )
                
                if booking_sessions.exists():
                    # Update the first session with new values
                    booking_session = booking_sessions.first()
                    
                    # Update the booking session with new values
                    booking_session.end_time = instance.end_time
                    booking_session.duration_minutes = instance.duration_minutes
                    booking_session.language = instance.language
                    booking_session.level = instance.level
                    booking_session.description = instance.description
                    booking_session.max_students = instance.max_students
                    booking_session.status = instance.status
                    
                    booking_session.save()
                    
                    # Sync students
                    booking_session.students.set(instance.students.all())
                    
                    # Delete any duplicate sessions beyond the first one
                    if booking_sessions.count() > 1:
                        for session in booking_sessions[1:]:
                            session.delete()
                else:
                    # Session doesn't exist in booking app, create it
                    booking_session = BookingGroupSession.objects.create(
                        title=instance.title,
                        instructor=booking_instructor,
                        language=instance.language,
                        level=instance.level,
                        description=instance.description,
                        start_time=instance.start_time,
                        end_time=instance.end_time,
                        duration_minutes=instance.duration_minutes,
                        max_students=instance.max_students,
                        price=instance.price if hasattr(instance, 'price') else 15.00,
                        status=instance.status
                    )
                    
                    # Sync students
                    booking_session.students.set(instance.students.all())
            except Instructor.DoesNotExist:
                # Instructor doesn't exist in booking app
                pass
    except (ImportError, AttributeError):
        # Booking app not available or models not compatible
        pass
    finally:
        _SYNCING_GROUP_SESSION = False