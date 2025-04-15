from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from .models import Profile
from web_project import TemplateLayout  # Import the TemplateLayout class

class DummyView:
    """A simple class to mimic the behavior of a class-based view for TemplateLayout"""
    def __init__(self, request):
        self.request = request

def register_view(request):
    """Register a new user"""
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        # Create user
        user = User.objects.create_user(username=username, email=email, password=password)
        
        # Set user type (teacher or student)
        is_teacher = request.POST.get('is_teacher') == 'true'
        is_student = request.POST.get('is_student') == 'true'
        
        user.is_teacher = is_teacher
        user.is_student = is_student
        user.save()
        
        # Update profile
        profile = user.profile
        profile.native_language = request.POST.get('native_language')
        profile.learning_language = request.POST.get('learning_language')
        profile.save()
        
        # Login the user
        login(request, user)
        
        return redirect('dashboard')
    
    # Initialize template context
    view_instance = DummyView(request)
    context = TemplateLayout.init(view_instance, {})
    return render(request, 'register.html', context)

def login_view(request):
    """Login existing user"""
    if request.method == 'POST':
        email_username = request.POST.get('email-username')
        password = request.POST.get('password')
        next_url = request.POST.get('next', 'dashboards:overview')  # Changed from 'index' to 'dashboards:overview'
        
        # Try to authenticate with email first
        user = None
        try:
            # Check if input is email
            if '@' in email_username:
                user = User.objects.get(email=email_username)
            else:
                # Otherwise use username
                user = User.objects.get(username=email_username)
                
            # Verify password
            if user.check_password(password):
                login(request, user)
                return redirect(next_url)
            else:
                user = None
        except User.DoesNotExist:
            pass
        
        if user is None:
            view_instance = DummyView(request)
            context = TemplateLayout.init(view_instance, {})
            messages.error(request, "Invalid email/username or password")
            return render(request, 'login.html', context)
    
    # Initialize template context for GET requests
    view_instance = DummyView(request)
    context = TemplateLayout.init(view_instance, {})
    return render(request, 'login.html', context)

    
def logout_view(request):
    """Logout user"""
    logout(request)
    return redirect('/')

@login_required
def profile_view(request, username=None):
    """View user profile"""
    if username:
        user = get_object_or_404(User, username=username)
    else:
        user = request.user
    
    view_instance = DummyView(request)
    context = TemplateLayout.init(view_instance, {'profile_user': user})
    return render(request, 'account/profile.html', context)

@login_required
def update_profile(request):
    """Update user profile"""
    if request.method == 'POST':
        profile = request.user.profile
        
        # Update profile fields
        profile.native_language = request.POST.get('native_language', profile.native_language)
        profile.learning_language = request.POST.get('learning_language', profile.learning_language)
        
        # Handle profile image upload
        if 'profile_image' in request.FILES:
            profile.profile_image = request.FILES['profile_image']
            
        profile.save()
        
        return redirect('profile')
    
    view_instance = DummyView(request)
    context = TemplateLayout.init(view_instance, {})
    return render(request, 'account/edit_profile.html', context)

@login_required
def get_profile_api(request):
    """API endpoint to get user profile information"""
    profile = request.user.profile
    return JsonResponse(profile.get_profile())

def forgot_password(request):
    """Password recovery view"""
    if request.method == 'POST':
        email = request.POST.get('email')
        try:
            user = User.objects.get(email=email)
            # Handle password reset logic here
            # For example, send reset email
            
            messages.success(request, "Password reset instructions sent to your email")
            return redirect('login')
        except User.DoesNotExist:
            messages.error(request, "Email not found in our system")
    
    view_instance = DummyView(request)
    context = TemplateLayout.init(view_instance, {})
    return render(request, 'account/forgot_password.html', context)

def reset_password(request, token=None):
    """Reset password view with token validation"""
    # Validate token and allow password reset
    if request.method == 'POST':
        # Handle password reset form submission
        pass
    
    view_instance = DummyView(request)
    context = TemplateLayout.init(view_instance, {'token': token})
    return render(request, 'account/reset_password.html', context)