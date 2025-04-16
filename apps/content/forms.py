from django import forms
from django.utils.text import slugify
from django.core.exceptions import ValidationError

from .models import (
    Course, LearningModule, Lesson, Resource, Language, LanguageLevel
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
            'attachment', 'duration_minutes', 'order'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Lesson Title'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 10, 'placeholder': 'Lesson Content'}),
            'video_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'Video URL (optional)'}),
            'audio_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'Audio URL (optional)'}),
            'attachment': forms.FileInput(attrs={'class': 'form-control'}),
            'duration_minutes': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
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
        # If it's a new lesson, we'll check in the form_valid method of the view
        # since we need to know which module it belongs to
        
        return title


class ResourceForm(forms.ModelForm):
    """Form for creating and editing resources"""
    class Meta:
        model = Resource
        fields = [
            'title', 'description', 'resource_type', 'file', 
            'external_url', 'language', 'level', 'is_public',
            'course', 'lesson'
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


class CourseFilterForm(forms.Form):
    """Form for filtering courses"""
    language = forms.ModelChoiceField(
        queryset=Language.objects.filter(is_active=True),
        required=False,
        empty_label="All Languages",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    level = forms.ModelChoiceField(
        queryset=LanguageLevel.objects.all(),
        required=False,
        empty_label="All Levels",
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


class ResourceFilterForm(forms.Form):
    """Form for filtering resources"""
    language = forms.ModelChoiceField(
        queryset=Language.objects.filter(is_active=True),
        required=False,
        empty_label="All Languages",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    level = forms.ModelChoiceField(
        queryset=LanguageLevel.objects.all(),
        required=False,
        empty_label="All Levels",
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