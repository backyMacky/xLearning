from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from apps.meetings.models import Meeting
from django.db.models.signals import post_save
from django.dispatch import receiver


class Instructor(models.Model):
    """Extended model for instructors"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='booking_instructor_profile')
    bio = models.TextField(blank=True, null=True)
    profile_image = models.ImageField(upload_to='instructor_images/', blank=True, null=True)
    # Changed from ManyToManyField to MultiSelectField or CharField
    teaching_languages = models.CharField(max_length=100, blank=True, help_text="Comma-separated language codes")
    specialties = models.ManyToManyField('InstructorSpecialty', related_name='booking_instructors', blank=True)
    hourly_rate = models.DecimalField(max_digits=6, decimal_places=2, default=25.00)
    teaching_style = models.TextField(blank=True, null=True)
    is_featured = models.BooleanField(default=False)
    is_available = models.BooleanField(default=True)
    availability_last_updated = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username} (Instructor)"
    
    @property
    def rating(self):
        """Calculate average rating from reviews"""
        reviews = InstructorReview.objects.filter(instructor=self)
        if reviews.exists():
            return round(sum(review.rating for review in reviews) / reviews.count(), 1)
        return 0
    
    @property
    def review_count(self):
        """Count number of reviews"""
        return InstructorReview.objects.filter(instructor=self).count()
    
    @property
    def sessions_completed(self):
        """Count completed sessions"""
        return PrivateSessionSlot.objects.filter(
            instructor=self,
            status='completed'
        ).count()

class InstructorSpecialty(models.Model):
    """Model for instructor specialties (e.g., Business English, Grammar, etc.)"""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)  # Added this field
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name_plural = "Instructor specialties"

class InstructorQualification(models.Model):
    """Model for instructor qualifications and certifications"""
    instructor = models.ForeignKey(Instructor, on_delete=models.CASCADE, related_name='qualifications')
    title = models.CharField(max_length=255)
    institution = models.CharField(max_length=255, blank=True, null=True)
    year = models.IntegerField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.title} - {self.instructor.user.username}"


class InstructorExperience(models.Model):
    """Model for instructor work experience"""
    instructor = models.ForeignKey(Instructor, on_delete=models.CASCADE, related_name='experiences')
    position = models.CharField(max_length=255)
    institution = models.CharField(max_length=255)
    years = models.CharField(max_length=100, help_text="E.g., '2018-2020'")
    description = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.position} at {self.institution} - {self.instructor.user.username}"


class PrivateSessionSlot(models.Model):
    """Model for managing private one-on-one session slots"""
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
    
    instructor = models.ForeignKey(Instructor, on_delete=models.CASCADE, related_name='private_slots')
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='booked_private_slots', 
                                null=True, blank=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    duration_minutes = models.IntegerField(default=60)
    language = models.CharField(max_length=10, choices=LANGUAGE_CHOICES, null=True)
    level = models.CharField(max_length=2, choices=LEVEL_CHOICES, null=True)
    status = models.CharField(max_length=20, choices=[
        ('available', 'Available'),
        ('booked', 'Booked'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], default='available')
    meeting = models.ForeignKey(Meeting, on_delete=models.SET_NULL, null=True, blank=True, 
                                related_name='private_session_slot')
    
    def __str__(self):
        status_text = f"[{self.status.upper()}]"
        if self.student:
            return f"{status_text} Private: {self.instructor.user.username} with {self.student.username} - {self.start_time.strftime('%Y-%m-%d %H:%M')}"
        return f"{status_text} Private: {self.instructor.user.username} - {self.start_time.strftime('%Y-%m-%d %H:%M')}"
    
    def save(self, *args, **kwargs):
        """Calculate end_time based on duration if not provided"""
        if not self.end_time and self.start_time and self.duration_minutes:
            self.end_time = self.start_time + timezone.timedelta(minutes=self.duration_minutes)
        super().save(*args, **kwargs)
    
    def book(self, student):
        """Book a private session slot for a student"""
        if self.status != 'available' or self.student is not None:
            return False, "This slot is no longer available"
            
        self.student = student
        self.status = 'booked'
        
        # Create a meeting for this session
        meeting = Meeting.objects.create(
            title=f"Private Session: {self.instructor.user.username} and {self.student.username}",
            teacher=self.instructor.user,
            start_time=self.start_time,
            duration=self.duration_minutes,
            meeting_link=f"https://meet.google.com/private-{self.instructor.user.username}-{self.student.username}-{timezone.now().strftime('%Y%m%d%H%M')}"
        )
        meeting.students.add(self.student)
        
        # Link meeting to session
        self.meeting = meeting
        self.save()
        
        return True, "Session booked successfully"
    
    def cancel(self, user):
        """Cancel a booked private session"""
        if self.status != 'booked':
            return False, "This session cannot be cancelled"
            
        # Check if the user has permission (either the student or instructor)
        if user != self.student and user != self.instructor.user:
            return False, "You don't have permission to cancel this session"
            
        # Check cancellation policy (e.g., 24-hour notice)
        if self.start_time - timezone.now() < timezone.timedelta(hours=24):
            # Late cancellation
            if user == self.student:
                # Student cancelling late - may incur a fee
                self.status = 'cancelled'
                if self.meeting:
                    self.meeting.delete()
                    self.meeting = None
                self.save()
                return True, "Session cancelled, but a cancellation fee may apply"
            else:
                # Instructor cancelling late
                self.status = 'cancelled'
                if self.meeting:
                    self.meeting.delete()
                    self.meeting = None
                self.student = None
                self.save()
                return True, "Session cancelled. The student will receive a full refund."
        else:
            # Normal cancellation with sufficient notice
            self.status = 'cancelled'
            if self.meeting:
                self.meeting.delete()
                self.meeting = None
            
            # Clear student reference if this is the instructor cancelling
            if user == self.instructor.user:
                self.student = None
            
            self.save()
            return True, "Session cancelled successfully"


class GroupSession(models.Model):
    """Model for group language sessions"""
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
    instructor = models.ForeignKey(Instructor, on_delete=models.CASCADE, related_name='group_sessions')
    language = models.CharField(max_length=10, choices=LANGUAGE_CHOICES)
    level = models.CharField(max_length=2, choices=LEVEL_CHOICES)
    description = models.TextField()
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    duration_minutes = models.IntegerField(default=90)
    max_students = models.IntegerField(default=8)
    students = models.ManyToManyField(User, related_name='enrolled_group_sessions', blank=True)
    price = models.DecimalField(max_digits=6, decimal_places=2)
    status = models.CharField(max_length=20, choices=[
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], default='scheduled')
    meeting = models.ForeignKey(Meeting, on_delete=models.SET_NULL, null=True, blank=True, 
                                related_name='group_session')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.title} - {self.instructor.user.username} - {self.start_time.strftime('%Y-%m-%d %H:%M')}"
    
    def save(self, *args, **kwargs):
        """Calculate end_time based on duration if not provided"""
        if not self.end_time and self.start_time and self.duration_minutes:
            self.end_time = self.start_time + timezone.timedelta(minutes=self.duration_minutes)
        super().save(*args, **kwargs)
    
    @property
    def is_full(self):
        """Check if the group session is full"""
        return self.students.count() >= self.max_students
    
    @property
    def enrollment_percentage(self):
        """Calculate percentage of seats filled"""
        if self.max_students > 0:
            return (self.students.count() / self.max_students) * 100
        return 0
    
    def enroll_student(self, student):
        """Enroll a student in the group session"""
        if self.is_full:
            return False, "This session is full"
            
        if student in self.students.all():
            return False, "You are already enrolled in this session"
            
        if self.start_time < timezone.now():
            return False, "Cannot enroll in a past session"
            
        self.students.add(student)
        
        # Create meeting if it doesn't exist yet
        if not self.meeting:
            meeting = Meeting.objects.create(
                title=f"Group Session: {self.title}",
                teacher=self.instructor.user,
                start_time=self.start_time,
                duration=self.duration_minutes,
                meeting_link=f"https://meet.google.com/group-{self.instructor.user.username}-{self.id}-{timezone.now().strftime('%Y%m%d')}"
            )
            self.meeting = meeting
            self.save()
        
        # Add student to meeting participants
        self.meeting.students.add(student)
        
        return True, "Successfully enrolled in the group session"
    
    def unenroll_student(self, student):
        """Remove a student from the group session"""
        if student not in self.students.all():
            return False, "You are not enrolled in this session"
            
        # Check cancellation policy (e.g., 24-hour notice)
        if self.start_time - timezone.now() < timezone.timedelta(hours=24):
            return False, "Cannot unenroll less than 24 hours before the session"
            
        self.students.remove(student)
        
        # Remove from meeting participants
        if self.meeting:
            self.meeting.students.remove(student)
        
        return True, "Successfully unenrolled from the group session"


class InstructorReview(models.Model):
    """Model for student reviews of instructors"""
    instructor = models.ForeignKey(Instructor, on_delete=models.CASCADE, related_name='reviews')
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='instructor_reviews')
    rating = models.IntegerField(choices=[(1, '1 - Poor'), (2, '2 - Fair'), (3, '3 - Good'), 
                                         (4, '4 - Very Good'), (5, '5 - Excellent')])
    comment = models.TextField()
    private_session = models.ForeignKey(PrivateSessionSlot, on_delete=models.SET_NULL, 
                                       null=True, blank=True, related_name='reviews')
    group_session = models.ForeignKey(GroupSession, on_delete=models.SET_NULL, 
                                     null=True, blank=True, related_name='reviews')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Review by {self.student.username} for {self.instructor.user.username} - {self.rating} stars"
    
    class Meta:
        unique_together = [
            ['student', 'private_session'],
            ['student', 'group_session']
        ]


class CreditTransaction(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='credit_transactions')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField()
    transaction_type = models.CharField(max_length=20, choices=[
        ('purchase', 'Purchase'),
        ('refund', 'Refund'),
        ('deduction', 'Deduction'),
        ('bonus', 'Bonus'),
    ])
    private_session = models.ForeignKey('PrivateSessionSlot', on_delete=models.SET_NULL, 
                                       null=True, blank=True, related_name='transactions')
    group_session = models.ForeignKey('GroupSession', on_delete=models.SET_NULL, 
                                     null=True, blank=True, related_name='transactions')
    created_at = models.DateTimeField(auto_now_add=True)

    def get_balance(self):
        """Calculate the current credit balance for the student"""
        # Sum credits from purchases, refunds, and bonuses
        credits = self.__class__.objects.filter(
            student=self.student,
            transaction_type__in=['purchase', 'refund', 'bonus']
        ).aggregate(total=models.Sum('amount'))['total'] or 0
        
        # Subtract deductions
        debits = self.__class__.objects.filter(
            student=self.student,
            transaction_type='deduction'
        ).aggregate(total=models.Sum('amount'))['total'] or 0
        
        return credits - debits


# Define the missing function for syncing from PrivateSession to PrivateSessionSlot
def sync_private_session_to_booking(sender, instance, created, **kwargs):
    """Sync content private session changes to booking app"""
    try:
        # Get booking instructor
        instructor = None
        if hasattr(instance.instructor.user, 'booking_instructor_profile'):
            instructor = instance.instructor.user.booking_instructor_profile
        else:
            return
            
        # Try to find matching booking slot
        try:
            booking_slot = PrivateSessionSlot.objects.get(
                instructor=instructor,
                start_time=instance.start_time
            )
            
            # Update booking slot with new values
            booking_slot.end_time = instance.end_time
            booking_slot.duration_minutes = instance.duration_minutes
            booking_slot.language = instance.language
            booking_slot.level = instance.level
            booking_slot.status = instance.status
            
            # Update student if booked
            if instance.status == 'booked' and instance.student:
                booking_slot.student = instance.student
            
            # Skip signal to avoid infinite loop
            post_save.disconnect(sync_booking_to_private_session, sender=PrivateSessionSlot)
            booking_slot.save()
            post_save.connect(sync_booking_to_private_session, sender=PrivateSessionSlot)
            
        except PrivateSessionSlot.DoesNotExist:
            # Create new booking slot
            booking_slot = PrivateSessionSlot(
                instructor=instructor,
                start_time=instance.start_time,
                end_time=instance.end_time,
                duration_minutes=instance.duration_minutes,
                language=instance.language,
                level=instance.level,
                status=instance.status,
                student=instance.student if instance.status == 'booked' else None
            )
            
            # Skip signal to avoid infinite loop
            post_save.disconnect(sync_booking_to_private_session, sender=PrivateSessionSlot)
            booking_slot.save()
            post_save.connect(sync_booking_to_private_session, sender=PrivateSessionSlot)
    
    except (ImportError, AttributeError):
        # Booking app not available or models not compatible
        pass


# Define the missing function for syncing from GroupSession to BookingGroupSession
def sync_group_session_to_booking(sender, instance, created, **kwargs):
    """Sync content group session changes to booking app"""
    try:
        # Get booking instructor
        instructor = None
        if hasattr(instance.instructor.user, 'booking_instructor_profile'):
            instructor = instance.instructor.user.booking_instructor_profile
        else:
            return
            
        # Try to find matching booking session
        try:
            booking_session = GroupSession.objects.get(
                instructor=instructor,
                start_time=instance.start_time,
                title=instance.title
            )
            
            # Update booking session with new values
            booking_session.end_time = instance.end_time
            booking_session.duration_minutes = instance.duration_minutes
            booking_session.language = instance.language
            booking_session.level = instance.level
            booking_session.description = instance.description
            booking_session.max_students = instance.max_students
            booking_session.status = instance.status
            
            # Skip signal to avoid infinite loop
            post_save.disconnect(sync_booking_to_group_session, sender=GroupSession)
            booking_session.save()
            post_save.connect(sync_booking_to_group_session, sender=GroupSession)
            
            # Sync students
            booking_session.students.set(instance.students.all())
            
        except GroupSession.DoesNotExist:
            # Create new booking session
            booking_session = GroupSession(
                title=instance.title,
                instructor=instructor,
                language=instance.language,
                level=instance.level,
                description=instance.description,
                start_time=instance.start_time,
                end_time=instance.end_time,
                duration_minutes=instance.duration_minutes,
                max_students=instance.max_students,
                status=instance.status,
                price=instance.price if hasattr(instance, 'price') else 15.00  # Default price
            )
            
            # Skip signal to avoid infinite loop
            post_save.disconnect(sync_booking_to_group_session, sender=GroupSession)
            booking_session.save()
            post_save.connect(sync_booking_to_group_session, sender=GroupSession)
            
            # Sync students
            booking_session.students.set(instance.students.all())
    
    except (ImportError, AttributeError):
        # Booking app not available or models not compatible
        pass


@receiver(post_save, sender=PrivateSessionSlot)
def sync_booking_to_private_session(sender, instance, created, **kwargs):
    """Sync booking slot changes to content app"""
    try:
        from apps.content.models import PrivateSession, Instructor as ContentInstructor
        
        # Skip if there's no corresponding content instructor
        if not hasattr(instance.instructor.user, 'instructor_profile'):
            return
            
        content_instructor = instance.instructor.user.instructor_profile
        
        # For existing slots, find the corresponding content session
        try:
            content_session = PrivateSession.objects.get(
                instructor=content_instructor,
                start_time=instance.start_time
            )
            
            # Update the content session with new values
            content_session.end_time = instance.end_time
            content_session.duration_minutes = instance.duration_minutes
            content_session.language = instance.language
            content_session.level = instance.level
            content_session.status = instance.status
            
            # Update student if booked
            if instance.status == 'booked' and instance.student:
                content_session.student = instance.student
            
            # Skip signal to avoid infinite loop
            post_save.disconnect(sync_private_session_to_booking, sender=PrivateSession)
            content_session.save()
            post_save.connect(sync_private_session_to_booking, sender=PrivateSession)
            
        except PrivateSession.DoesNotExist:
            # Session doesn't exist in content app, create it
            content_session = PrivateSession(
                instructor=content_instructor,
                start_time=instance.start_time,
                end_time=instance.end_time,
                duration_minutes=instance.duration_minutes,
                language=instance.language,
                level=instance.level,
                status=instance.status,
                student=instance.student if instance.status == 'booked' else None
            )
            
            # Skip signal to avoid infinite loop
            post_save.disconnect(sync_private_session_to_booking, sender=PrivateSession)
            content_session.save()
            post_save.connect(sync_private_session_to_booking, sender=PrivateSession)
    except (ImportError, AttributeError):
        # Content app not available or models not compatible
        pass


@receiver(post_save, sender=GroupSession)
def sync_booking_to_group_session(sender, instance, created, **kwargs):
    """Sync booking group session changes to content app"""
    try:
        from apps.content.models import GroupSession as ContentGroupSession
        
        # Skip if there's no corresponding content instructor
        if not hasattr(instance.instructor.user, 'instructor_profile'):
            return
            
        content_instructor = instance.instructor.user.instructor_profile
        
        # For existing sessions, find the corresponding content session
        try:
            content_session = ContentGroupSession.objects.get(
                instructor=content_instructor,
                start_time=instance.start_time,
                title=instance.title
            )
            
            # Update the content session with new values
            content_session.end_time = instance.end_time
            content_session.duration_minutes = instance.duration_minutes
            content_session.language = instance.language
            content_session.level = instance.level
            content_session.description = instance.description
            content_session.max_students = instance.max_students
            content_session.status = instance.status
            
            # Skip signal to avoid infinite loop
            post_save.disconnect(sync_group_session_to_booking, sender=ContentGroupSession)
            content_session.save()
            post_save.connect(sync_group_session_to_booking, sender=ContentGroupSession)
            
            # Sync students
            content_session.students.set(instance.students.all())
            
        except ContentGroupSession.DoesNotExist:
            # Session doesn't exist in content app, create it
            content_session = ContentGroupSession(
                title=instance.title,
                instructor=content_instructor,
                language=instance.language,
                level=instance.level,
                description=instance.description,
                start_time=instance.start_time,
                end_time=instance.end_time,
                duration_minutes=instance.duration_minutes,
                max_students=instance.max_students,
                status=instance.status
            )
            
            # Skip signal to avoid infinite loop
            post_save.disconnect(sync_group_session_to_booking, sender=ContentGroupSession)
            content_session.save()
            post_save.connect(sync_group_session_to_booking, sender=ContentGroupSession)
            
            # Sync students
            content_session.students.set(instance.students.all())
    except (ImportError, AttributeError):
        # Content app not available or models not compatible
        pass


# Connect the signals for content app if available
try:
    from apps.content.models import PrivateSession, GroupSession as ContentGroupSession
    post_save.connect(sync_private_session_to_booking, sender=PrivateSession)
    post_save.connect(sync_group_session_to_booking, sender=ContentGroupSession)
except ImportError:
    # Content app not available
    pass