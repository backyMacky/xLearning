from django import forms
from django.utils.text import slugify
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import (
    Course, LearningModule, Lesson, PrivateSession, GroupSession,
    Resource, Instructor, InstructorReview, SessionFeedback
)


class CourseFilterForm(forms.Form):
    """Form for filtering courses"""
    language = forms.ChoiceField(
        choices=[('', 'All Languages')] + Course.LANGUAGE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    level = forms.ChoiceField(
        choices=[('', 'All Levels')] + Course.LEVEL_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    q = forms.CharField(
        required=False,
        label="Search",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search courses...'
        })
    )


class CourseForm(forms.ModelForm):
    """Form for creating and editing courses"""
    class Meta:
        model = Course
        fields = [
            'title', 'description', 'language', 'level', 
            'image', 'is_featured', 'is_published', 'duration_weeks'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Course Title'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Course Description'}),
            'language': forms.Select(attrs={'class': 'form-select'}),
            'level': forms.Select(attrs={'class': 'form-select'}),
            'duration_weeks': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
            'is_featured': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_published': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }
    
    def clean_title(self):
        """Validate the title is unique"""
        title = self.cleaned_data.get('title')
        slug = slugify(title)
        
        # Check if the slug exists and it's not this course's slug
        if self.instance.pk:
            if Course.objects.filter(slug=slug).exclude(pk=self.instance.pk).exists():
                raise ValidationError("A course with a similar title already exists.")
        else:
            if Course.objects.filter(slug=slug).exists():
                raise ValidationError("A course with a similar title already exists.")
        
        return title


class ModuleForm(forms.ModelForm):
    """Form for creating and editing learning modules"""
    class Meta:
        model = LearningModule
        fields = ['title', 'description', 'order']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Module Title'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Module Description'}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'min': 0})
        }


class LessonForm(forms.ModelForm):
    """Form for creating and editing lessons"""
    class Meta:
        model = Lesson
        fields = [
            'title', 'content', 'video_url', 'audio_url', 
            'attachment', 'duration_minutes', 'tags', 'order'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Lesson Title'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 10, 'placeholder': 'Lesson Content', 'id': 'editor'}),
            'video_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'Video URL (optional)'}),
            'audio_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'Audio URL (optional)'}),
            'attachment': forms.FileInput(attrs={'class': 'form-control'}),
            'duration_minutes': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'tags': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Comma-separated tags'}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'min': 0})
        }
    
    def clean_title(self):
        """Validate the title is unique within the module"""
        title = self.cleaned_data.get('title')
        slug = slugify(title)
        
        # If this is an existing lesson being edited
        if self.instance.pk:
            if Lesson.objects.filter(
                module=self.instance.module, 
                slug=slug
            ).exclude(pk=self.instance.pk).exists():
                raise ValidationError("A lesson with a similar title already exists in this module.")
        # For new lessons, module will be set in the view
        
        return title

    def generate_keywords(self):
        """Generate keywords from content automatically"""
        if self.instance and hasattr(self.instance, 'generate_keywords'):
            self.instance.generate_keywords()


class ResourceForm(forms.ModelForm):
    """Form for creating and editing resources"""
    class Meta:
        model = Resource
        fields = [
            'title', 'description', 'resource_type', 'file', 
            'external_url', 'language', 'level', 'is_public',
            'course', 'lesson', 'tags'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Resource Title'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Resource Description'}),
            'resource_type': forms.Select(attrs={'class': 'form-select'}),
            'file': forms.FileInput(attrs={'class': 'form-control'}),
            'external_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'External URL (if applicable)'}),
            'language': forms.Select(attrs={'class': 'form-select'}),
            'level': forms.Select(attrs={'class': 'form-select'}),
            'course': forms.Select(attrs={'class': 'form-select'}),
            'lesson': forms.Select(attrs={'class': 'form-select'}),
            'tags': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Comma-separated tags'}),
            'is_public': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super(ResourceForm, self).__init__(*args, **kwargs)
        
        # If user is provided, filter course choices
        if user:
            self.fields['course'].queryset = Course.objects.filter(teacher=user)
            
            # Filter lessons based on teacher's courses
            if self.fields.get('lesson'):
                self.fields['lesson'].queryset = Lesson.objects.filter(
                    module__course__teacher=user
                )
    
    def clean(self):
        cleaned_data = super().clean()
        file = cleaned_data.get('file')
        external_url = cleaned_data.get('external_url')
        resource_type = cleaned_data.get('resource_type')
        
        # Validate file upload or external URL based on resource type
        if resource_type in ['document', 'image', 'audio', 'video', 'exercise', 'vocabulary']:
            if not file and not external_url:
                raise ValidationError("Either a file or external URL must be provided.")
        
        if resource_type == 'link' and not external_url:
            raise ValidationError("External URL is required for link resources.")
        
        return cleaned_data


class ResourceFilterForm(forms.Form):
    """Form for filtering resources"""
    language = forms.ChoiceField(
        choices=[('', 'All Languages')] + Course.LANGUAGE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    level = forms.ChoiceField(
        choices=[('', 'All Levels')] + Course.LEVEL_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    resource_type = forms.ChoiceField(
        choices=[('', 'All Types')] + Resource.RESOURCE_TYPES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    q = forms.CharField(
        required=False,
        label="Search",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search resources...'
        })
    )


class InstructorProfileForm(forms.ModelForm):
    """Form for creating and updating instructor profiles"""
    class Meta:
        model = Instructor
        fields = [
            'bio', 'teaching_style', 'profile_image', 'teaching_languages',
            'specialties', 'hourly_rate', 'is_available',
        ]
        widgets = {
            'bio': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Briefly introduce yourself and your qualifications'
            }),
            'teaching_style': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Describe your teaching approach'
            }),
            'profile_image': forms.FileInput(attrs={
                'class': 'form-control d-none',
                'accept': 'image/*'
            }),
            'teaching_languages': forms.SelectMultiple(attrs={
                'class': 'form-select select2'
            }),
            'specialties': forms.SelectMultiple(attrs={
                'class': 'form-select select2'
            }),
            'hourly_rate': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '5',
                'step': '0.01'
            }),
            'is_available': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super(InstructorProfileForm, self).__init__(*args, **kwargs)
        # Make hourly_rate optional by setting required=False
        self.fields['hourly_rate'].required = False
        
    def clean_hourly_rate(self):
        """Set default value for hourly_rate if not provided"""
        hourly_rate = self.cleaned_data.get('hourly_rate')
        if hourly_rate is None or hourly_rate == '':
            return 25.00  # Default value from the model
        return hourly_rate

class PrivateSessionForm(forms.ModelForm):
    """Form for creating private session slots"""
    class Meta:
        model = PrivateSession
        fields = [
            'language', 'level', 'duration_minutes', 'is_trial'
        ]
        widgets = {
            'language': forms.Select(attrs={'class': 'form-select'}),
            'level': forms.Select(attrs={'class': 'form-select'}),
            'duration_minutes': forms.Select(attrs={
                'class': 'form-select'
            }, choices=[(30, '30 minutes'), (45, '45 minutes'), (60, '1 hour'), (90, '1.5 hours'), (120, '2 hours')]),
            'is_trial': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }
    
    # Add extra fields for date and time
    session_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-control flatpickr-date',
            'placeholder': 'Select date',
            'required': 'true'
        })
    )
    
    session_time = forms.TimeField(
        widget=forms.TimeInput(attrs={
            'class': 'form-control flatpickr-time',
            'placeholder': 'Select time',
            'required': 'true'
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        session_date = cleaned_data.get('session_date')
        session_time = cleaned_data.get('session_time')
        
        if session_date and session_time:
            # Combine date and time into a datetime object
            start_time = timezone.datetime.combine(
                session_date, 
                session_time,
                tzinfo=timezone.get_current_timezone()
            )
            
            # Check if the start time is in the future
            if start_time < timezone.now():
                raise ValidationError("Session start time must be in the future.")
            
            # Add the start_time to cleaned_data
            cleaned_data['start_time'] = start_time
            
            # Calculate end_time based on duration
            duration = int(cleaned_data.get('duration_minutes', 60))
            cleaned_data['end_time'] = start_time + timezone.timedelta(minutes=duration)
        
        return cleaned_data
    
    def save(self, commit=True, instructor=None):
        instance = super().save(commit=False)
        
        # Set start and end time from form data
        instance.start_time = self.cleaned_data['start_time']
        instance.end_time = self.cleaned_data['end_time']
        
        # Set instructor if provided
        if instructor:
            instance.instructor = instructor
        
        if commit:
            instance.save()
        
        return instance


class GroupSessionForm(forms.ModelForm):
    """Form for creating group sessions"""
    class Meta:
        model = GroupSession
        fields = [
            'title', 'description', 'language', 'level', 
            'duration_minutes', 'max_students', 'min_students',
            'price', 'tags'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter a descriptive title for your session',
                'required': 'true'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Describe what students will learn in this session',
                'required': 'true'
            }),
            'language': forms.Select(attrs={'class': 'form-select'}),
            'level': forms.Select(attrs={'class': 'form-select'}),
            'duration_minutes': forms.Select(attrs={
                'class': 'form-select',
                'required': 'true'
            }, choices=[(30, '30 minutes'), (45, '45 minutes'), (60, '1 hour'), (90, '1.5 hours'), (120, '2 hours')]),
            'max_students': forms.Select(attrs={
                'class': 'form-select'
            }, choices=[(5, '5 students'), (10, '10 students'), (15, '15 students'), (20, '20 students'), (30, '30 students')]),
            'min_students': forms.Select(attrs={
                'class': 'form-select'
            }, choices=[(1, '1 student (no minimum)'), (2, '2 students'), (3, '3 students'), (5, '5 students')]),
            'price': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '5',
                'step': '0.01'
            }),
            'tags': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. conversation, grammar, business'
            })
        }
    
    # Add extra fields for date and time
    session_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-control flatpickr-date',
            'placeholder': 'Select date',
            'required': 'true'
        })
    )
    
    session_time = forms.TimeField(
        widget=forms.TimeInput(attrs={
            'class': 'form-control flatpickr-time',
            'placeholder': 'Select time',
            'required': 'true'
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        session_date = cleaned_data.get('session_date')
        session_time = cleaned_data.get('session_time')
        min_students = cleaned_data.get('min_students')
        max_students = cleaned_data.get('max_students')
        
        if min_students and max_students and min_students > max_students:
            raise ValidationError("Minimum students cannot be greater than maximum students.")
        
        if session_date and session_time:
            # Combine date and time into a datetime object
            start_time = timezone.datetime.combine(
                session_date, 
                session_time,
                tzinfo=timezone.get_current_timezone()
            )
            
            # Check if the start time is in the future
            if start_time < timezone.now():
                raise ValidationError("Session start time must be in the future.")
            
            # Add the start_time to cleaned_data
            cleaned_data['start_time'] = start_time
            
            # Calculate end_time based on duration
            duration = int(cleaned_data.get('duration_minutes', 60))
            cleaned_data['end_time'] = start_time + timezone.timedelta(minutes=duration)
        
        return cleaned_data
    
    def save(self, commit=True, instructor=None):
        instance = super().save(commit=False)
        
        # Set start and end time from form data
        instance.start_time = self.cleaned_data['start_time']
        instance.end_time = self.cleaned_data['end_time']
        
        # Set instructor if provided
        if instructor:
            instance.instructor = instructor
        
        if commit:
            instance.save()
        
        return instance
    

class SessionFeedbackForm(forms.ModelForm):
    """Form for students to provide feedback after a session"""
    class Meta:
        model = SessionFeedback
        fields = [
            'rating', 'teaching_quality', 'technical_quality', 
            'content_relevance', 'comment'
        ]
        widgets = {
            'rating': forms.RadioSelect(attrs={'class': 'rating-input'}),
            'teaching_quality': forms.RadioSelect(attrs={'class': 'rating-input'}),
            'technical_quality': forms.RadioSelect(attrs={'class': 'rating-input'}),
            'content_relevance': forms.RadioSelect(attrs={'class': 'rating-input'}),
            'comment': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Share your experience with this session'
            })
        }


class InstructorReviewForm(forms.ModelForm):
    """Form for students to review instructors"""
    class Meta:
        model = InstructorReview
        fields = ['rating', 'comment']
        widgets = {
            'rating': forms.RadioSelect(attrs={'class': 'rating-input'}),
            'comment': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Share your experience with this instructor'
            })
        }