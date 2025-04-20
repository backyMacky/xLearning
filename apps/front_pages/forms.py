from django import forms
from django.utils.translation import gettext_lazy as _
from .models import ContactMessage, Subscriber

class ContactForm(forms.ModelForm):
    """Form for contact page submissions"""
    
    class Meta:
        model = ContactMessage
        fields = ['name', 'email', 'subject', 'message']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Your Full Name'),
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': _('Your Email Address'),
            }),
            'subject': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Message Subject'),
            }),
            'message': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': _('Your Message'),
                'rows': 6,
            }),
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.required = True

class SubscriberForm(forms.ModelForm):
    """Form for newsletter subscription"""
    
    class Meta:
        model = Subscriber
        fields = ['email']
        widgets = {
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': _('Your email'),
            }),
        }