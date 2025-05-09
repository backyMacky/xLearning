from django.http import JsonResponse, HttpResponseRedirect
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView, FormView, View
from django.contrib.auth.models import Permission
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.db.models import Q
from django.core.paginator import Paginator
from django.contrib.auth import login, authenticate, logout
from django.conf import settings
from django.utils import timezone
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import send_mail
from django.db.models import Sum
import random
import string

# Additional imports needed
from django.template.loader import render_to_string
from django.utils.html import strip_tags
import uuid
import datetime

from web_project import TemplateLayout
from web_project.template_helpers.theme import TemplateHelper
from apps.account.services import NotificationService
from .models import Notification, NotificationType, Role, UserRole, Profile, UserType, CustomUser

# Mixin for handling template layout (placeholder implementation)
class TemplateLayoutMixin:
    """Mixin to provide template layout functionality"""
    pass

# Base View for account app - Using the same pattern as front_page app
class BaseAccountView(TemplateView):
    """Base class for all account views to ensure consistent template handling"""
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        # Set consistent layout properties for all account pages
        context.update({
            "layout": "front",  # Use the front layout like front_page app
            "layout_path": TemplateHelper.set_layout("layout_front.html", context),
            "active_url": self.request.path,
            "is_front": True,  # This is consistent with front_page app
        })
        
        # Map context variables to template variables
        TemplateHelper.map_context(context)
        
        return context

# Base Mixins for authenticated views
class SuperUserAccessMixin(UserPassesTestMixin):
    """Mixin to ensure superusers can access everything"""
    def test_func(self):
        return self.request.user.is_superuser

class AdminRequiredMixin(UserPassesTestMixin):
    """Mixin to ensure only admin users can access view"""
    def test_func(self):
        return self.request.user.is_authenticated and (self.request.user.is_admin() or self.request.user.is_superuser)

# Authentication Views
class RegisterView(BaseAccountView, View):
    """Class-based view for user registration - all users register as students by default"""
    template_name = 'register.html'
    success_url = reverse_lazy('account:verify_email')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "page_title": "Create an Account",
            "page_description": "Join xLearning and start your learning journey."
        })
        return context
    
    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context_data())
    
    def post(self, request, *args, **kwargs):
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        first_name = request.POST.get('first_name', '')
        last_name = request.POST.get('last_name', '')
        native_language = request.POST.get('native_language', '')
        learning_language = request.POST.get('learning_language', '')
        
        # Check if user already exists
        if CustomUser.objects.filter(username=username).exists():
            messages.error(request, "Username already exists")
            return redirect('account:register')
        if CustomUser.objects.filter(email=email).exists():
            messages.error(request, "Email already exists")
            return redirect('account:register')
        
        # Create user - always as student by default
        user = CustomUser.objects.create_user(
            username=username, 
            email=email, 
            password=password,
            first_name=first_name,
            last_name=last_name
        )
        
        # Set user type to student by default
        user.user_type = UserType.STUDENT
        
        # Generate verification token
        token = str(uuid.uuid4())
        user.verification_token = token
        user.save()
        
        # Update profile
        profile = user.profile
        profile.native_language = native_language
        profile.learning_language = learning_language
        profile.save()
        
        # Send welcome and verification email
        self.send_welcome_verification_email(request, user, token)
        
        # Create success message
        messages.success(request, "Registration successful! Please check your email to verify your account.")
        
        # Redirect to verification page
        return redirect(self.success_url)
    
    def send_welcome_verification_email(self, request, user, token):
        """Send welcome and verification email"""
        verify_url = request.build_absolute_uri(
            reverse('account:verify_email_confirm', kwargs={'token': token})
        )
        
        context = {
            'user': user,
            'verify_url': verify_url,
            'site_name': 'xLearning',
            'site_url': request.build_absolute_uri('/'),
        }
        
        # Render HTML email template
        html_message = render_to_string('email/welcome_verification.html', context)
        plain_message = strip_tags(html_message)
        
        subject = 'Welcome to xLearning - Verify Your Account'
        email_from = settings.DEFAULT_FROM_EMAIL
        recipient_list = [user.email]
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=email_from,
            recipient_list=recipient_list,
            html_message=html_message,
            fail_silently=False
        )

class LoginView(BaseAccountView, View):
    """Class-based view for user login"""
    template_name = 'login.html'
    
    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context_data())
    
    def post(self, request, *args, **kwargs):
        email_username = request.POST.get('email-username')
        password = request.POST.get('password')
        next_url = request.POST.get('next', '')

        # Try to authenticate with email or username
        user = None
        try:
            # Check if input is email
            if '@' in email_username:
                user = CustomUser.objects.get(email=email_username)
            else:
                # Otherwise use username
                user = CustomUser.objects.get(username=email_username)

            # Verify password
            if user.check_password(password):
                # Check if email is verified (skip for superusers)
                if not user.is_verified and user.user_type != UserType.ADMIN and not user.is_superuser:
                    messages.warning(request, "Please verify your email address before logging in.")
                    return redirect('account:verify_email')

                login(request, user)

                # Check if this is first login for student who registered through the normal form
                if user.first_login and user.user_type == UserType.STUDENT and not user.created_by_admin:
                    user.first_login = False
                    user.save()
                    return redirect('booking:purchase_credits')

                # Normal redirection
                return redirect(next_url if next_url else 'dashboards:overview')
            else:
                user = None
        except CustomUser.DoesNotExist:
            pass
        
        if user is None:
            messages.error(request, "Invalid email/username or password")
            return render(request, 'login.html', self.get_context_data())

        return HttpResponseRedirect(request.get_full_path())

class LogoutView(View):
    """Class-based view for user logout"""
    def get(self, request, *args, **kwargs):
        logout(request)
        return redirect('front_pages:home')  # Redirect to home page instead of /

class VerifyEmailView(BaseAccountView):
    """Class-based view to verify email address"""
    template_name = 'verify_email.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "page_title": "Verify Your Email",
            "page_description": "Complete your registration by verifying your email address."
        })
        return context
    
    def get(self, request, *args, **kwargs):
        token = kwargs.get('token')
        if token:
            try:
                user = CustomUser.objects.get(verification_token=token)
                user.is_verified = True
                user.verification_token = None
                user.save()
                messages.success(request, "Email verification successful! You can now log in.")
                return redirect('account:login')
            except CustomUser.DoesNotExist:
                messages.error(request, "Invalid verification token.")
        
        return super().get(request, *args, **kwargs)

class ResendVerificationEmailView(BaseAccountView, View):
    """Class-based view to resend verification email"""
    def post(self, request, *args, **kwargs):
        email = request.POST.get('email')
        try:
            user = CustomUser.objects.get(email=email)
            if user.is_verified:
                messages.info(request, "Your email is already verified.")
                return redirect('account:login')
            
            # Generate new token
            token = str(uuid.uuid4())
            user.verification_token = token
            user.save()
            
            # Send verification email
            verify_url = request.build_absolute_uri(
                reverse('account:verify_email_confirm', kwargs={'token': token})
            )
            
            subject = 'Verify your email address'
            message = f'Hi {user.username},\n\nPlease click the link below to verify your email address:\n\n{verify_url}\n\nThanks!'
            email_from = settings.DEFAULT_FROM_EMAIL
            recipient_list = [user.email]
            
            send_mail(subject, message, email_from, recipient_list)
            
            messages.success(request, "Verification email sent! Please check your inbox.")
        except CustomUser.DoesNotExist:
            messages.error(request, "No account found with that email address.")
        
        return redirect('account:verify_email')

class ForgotPasswordView(BaseAccountView, View):
    """Class-based view for password recovery"""
    template_name = 'forgot_password.html'
    success_url = reverse_lazy('account:login')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "page_title": "Forgot Password",
            "page_description": "Reset your password to regain access to your account."
        })
        return context
    
    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context_data())
    
    def post(self, request, *args, **kwargs):
        email = request.POST.get('email')
        try:
            user = CustomUser.objects.get(email=email)
            
            # Generate reset token
            token = str(uuid.uuid4())
            user.reset_password_token = token
            user.reset_password_expiry = timezone.now() + datetime.timedelta(hours=24)
            user.save()
            
            # Send reset email
            reset_url = request.build_absolute_uri(
                reverse('account:reset_password', kwargs={'token': token})
            )
            
            subject = 'Reset your password'
            message = f'Hi {user.username},\n\nPlease click the link below to reset your password:\n\n{reset_url}\n\nThis link will expire in 24 hours.\n\nThanks!'
            email_from = settings.DEFAULT_FROM_EMAIL
            recipient_list = [user.email]
            
            send_mail(subject, message, email_from, recipient_list)
            
            messages.success(request, "Password reset instructions sent to your email")
            return redirect(self.success_url)
        except CustomUser.DoesNotExist:
            messages.error(request, "Email not found in our system")
            return self.render_to_response(self.get_context_data())

class ResetPasswordView(BaseAccountView, View):
    """Class-based view for resetting password with token validation"""
    template_name = 'reset_password.html'
    success_url = reverse_lazy('account:login')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "page_title": "Reset Password",
            "page_description": "Create a new password for your account.",
            "token": self.kwargs.get('token')
        })
        return context
    
    def get(self, request, *args, **kwargs):
        token = kwargs.get('token')
        try:
            user = CustomUser.objects.get(reset_password_token=token)
            
            # Check if token has expired
            if user.reset_password_expiry < timezone.now():
                messages.error(request, "Password reset link has expired. Please request a new one.")
                return redirect('account:forgot_password')
                
        except CustomUser.DoesNotExist:
            messages.error(request, "Invalid password reset link.")
            return redirect('account:forgot_password')
            
        return render(request, self.template_name, self.get_context_data())
    
    def post(self, request, *args, **kwargs):
        token = kwargs.get('token')
        try:
            user = CustomUser.objects.get(reset_password_token=token)
            
            # Check if token has expired
            if user.reset_password_expiry < timezone.now():
                messages.error(request, "Password reset link has expired. Please request a new one.")
                return redirect('account:forgot_password')
            
            password = request.POST.get('password')
            confirm_password = request.POST.get('confirm-password')
            
            if password != confirm_password:
                messages.error(request, "Passwords do not match.")
                return render(request, self.template_name, self.get_context_data())
            
            # Set new password
            user.set_password(password)
            user.reset_password_token = None
            user.reset_password_expiry = None
            user.save()
            
            messages.success(request, "Password has been reset successfully! You can now log in.")
            return redirect(self.success_url)
            
        except CustomUser.DoesNotExist:
            messages.error(request, "Invalid password reset link.")
            return redirect('account:forgot_password')

# Profile Views
class ProfileView(LoginRequiredMixin, BaseAccountView, DetailView):
    """Class-based view for viewing user profile"""
    model = CustomUser
    template_name = 'profile.html'
    context_object_name = 'profile_user'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.get_object()
        
        context.update({
            "page_title": f"{user.username}'s Profile",
            "page_description": "View and manage your account details."
        })
        
        # Add statistics based on user type
        if user.is_teacher():
            # Teacher statistics
            taught_courses = getattr(user, 'taught_courses', [])
            if hasattr(taught_courses, 'count'):
                context['taught_courses'] = taught_courses.count()
            else:
                context['taught_courses'] = 0
            
            # Count unique students
            total_students = 0
            if hasattr(taught_courses, 'all'):
                student_ids = set()
                for course in taught_courses.all():
                    if hasattr(course, 'students') and hasattr(course.students, 'values_list'):
                        student_ids.update(course.students.values_list('id', flat=True))
                total_students = len(student_ids)
            context['total_students'] = total_students
            
            # Calculate teaching hours (placeholder)
            context['teaching_hours'] = 0
        else:
            # Student statistics
            if hasattr(user, 'enrolled_courses') and hasattr(user.enrolled_courses, 'count'):
                context['enrolled_courses'] = user.enrolled_courses.count()
            else:
                context['enrolled_courses'] = 0
            
            # Placeholder for completed lessons
            context['completed_lessons'] = 0
            context['avg_score'] = 0
        
        return context
    
    def get_object(self, queryset=None):
        username = self.kwargs.get('username')
        if username:
            return get_object_or_404(CustomUser, username=username)
        return self.request.user

class UpdateProfileView(LoginRequiredMixin, BaseAccountView, UpdateView):
    """Class-based view for updating user profile"""
    model = Profile
    template_name = 'edit_profile.html'
    fields = ['native_language', 'learning_language', 'bio', 'phone_number', 'date_of_birth', 'profile_image']
    success_url = reverse_lazy('account:profile')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "page_title": "Edit Profile",
            "page_description": "Update your profile information."
        })
        return context
    
    def get_object(self, queryset=None):
        return self.request.user.profile
    
    def form_valid(self, form):
        user = self.request.user
        
        # Update user fields from POST
        user.username = self.request.POST.get('username', user.username)
        user.email = self.request.POST.get('email', user.email)
        user.first_name = self.request.POST.get('first_name', user.first_name)
        user.last_name = self.request.POST.get('last_name', user.last_name)
        user.save()
        
        # Handle profile image separately
        profile_image = self.request.FILES.get('profile_image')
        if profile_image:
            form.instance.profile_image = profile_image
        
        # Handle date of birth separately if needed
        dob_str = self.request.POST.get('date_of_birth')
        if dob_str:
            try:
                form.instance.date_of_birth = datetime.datetime.strptime(dob_str, '%Y-%m-%d').date()
            except ValueError:
                # Handle invalid date format
                pass
        
        messages.success(self.request, "Profile updated successfully!")
        return super().form_valid(form)

class ProfileAPIView(LoginRequiredMixin, View):
    """Class-based API view to get user profile information"""
    def get(self, request, *args, **kwargs):
        profile = request.user.profile
        return JsonResponse(profile.get_profile())

class TeacherRequestView(LoginRequiredMixin, BaseAccountView, View):
    """View for students to request teacher privileges"""
    template_name = 'teacher_request.html'
    success_url = reverse_lazy('account:profile')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "page_title": "Request Teacher Status",
            "page_description": "Submit your request to become a teacher on the platform."
        })
        return context
    
    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context_data())
    
    def post(self, request, *args, **kwargs):
        # Make sure the user is a student
        if request.user.user_type != UserType.STUDENT:
            messages.error(request, "You are already a teacher or have a different role.")
            return redirect('account:profile')
            
        # Get request details
        qualifications = request.POST.get('qualifications', '')
        experience = request.POST.get('experience', '')
        teaching_subjects = request.POST.get('teaching_subjects', '')
        additional_info = request.POST.get('additional_info', '')
        
        # Update user profile
        profile = request.user.profile
        profile.teacher_request_pending = True
        profile.teacher_request_date = timezone.now()
        profile.teacher_qualifications = qualifications
        profile.teacher_experience = experience
        profile.teacher_subjects = teaching_subjects
        profile.save()
        
        # Create a notification for admins
        admin_users = CustomUser.objects.filter(is_superuser=True) | CustomUser.objects.filter(user_type=UserType.ADMIN)
        
        message_content = f"""
        User {request.user.username} ({request.user.email}) has requested teacher status.
        
        Qualifications: {qualifications}
        Experience: {experience}
        Teaching Subjects: {teaching_subjects}
        Additional Info: {additional_info}
        """
        
        # Create notifications for all admins
        for admin in admin_users:
            NotificationService.send_notification(
                recipient=admin,
                title=f"Teacher Status Request from {request.user.username}",
                message=message_content,
                notification_type=NotificationType.SYSTEM,
                sender=request.user,
                action_url=reverse('account:user_detail', kwargs={'pk': request.user.id})
            )
        
        messages.success(request, "Your request to become a teacher has been submitted. An administrator will review your request and get back to you soon.")
        return redirect(self.success_url)

class TeacherApprovalView(LoginRequiredMixin, AdminRequiredMixin, View):
    """View for admins to approve or reject teacher requests"""
    def post(self, request, *args, **kwargs):
        user_id = kwargs.get('user_id')
        user = get_object_or_404(CustomUser, id=user_id)
        action = request.POST.get('action')
        
        # Check if user is a student and has a pending request
        if not hasattr(user.profile, 'teacher_request_pending') or not user.profile.teacher_request_pending:
            messages.error(request, "This user does not have a pending teacher request.")
            return redirect('account:user_detail', pk=user_id)
        
        if action == 'approve':
            # Update user type to teacher
            user.user_type = UserType.TEACHER
            user.save()
            
            # Clear pending flag
            user.profile.teacher_request_pending = False
            user.profile.teacher_approved_date = timezone.now()
            user.profile.save()
            
            # Notify the user
            NotificationService.send_notification(
                recipient=user,
                title="Teacher Status Approved",
                message="Congratulations! Your request to become a teacher has been approved. You now have teacher privileges on the platform.",
                notification_type=NotificationType.SUCCESS,
                sender=request.user
            )
            
            messages.success(request, f"User {user.username} has been approved as a teacher.")
        
        elif action == 'reject':
            # Clear pending flag
            user.profile.teacher_request_pending = False
            user.profile.save()
            
            # Get rejection reason
            reason = request.POST.get('rejection_reason', 'Your request did not meet our current requirements.')
            
            # Notify the user
            NotificationService.send_notification(
                recipient=user,
                title="Teacher Status Request Declined",
                message=f"We regret to inform you that your request to become a teacher has been declined for the following reason: {reason}",
                notification_type=NotificationType.INFO,
                sender=request.user
            )
            
            messages.success(request, f"User {user.username}'s teacher request has been rejected.")
        
        return redirect('account:user_detail', pk=user_id)

# Notification Views
class NotificationListView(LoginRequiredMixin, BaseAccountView, ListView):
    """Class-based view to list user notifications"""
    model = Notification
    template_name = 'notification_list.html'
    context_object_name = 'notifications'
    paginate_by = 10
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "page_title": "Notifications",
            "page_description": "View your notifications and stay updated.",
            "notification_types": NotificationType.choices,
            "selected_type": self.request.GET.get('type', ''),
            "selected_read_status": self.request.GET.get('read_status', ''),
            "unread_count": NotificationService.get_unread_count(self.request.user)
        })
        return context
    
    def get_queryset(self):
        queryset = Notification.objects.filter(recipient=self.request.user).order_by('-created_at')
        
        # Apply filters
        filter_type = self.request.GET.get('type', '')
        if filter_type:
            queryset = queryset.filter(notification_type=filter_type)
        
        read_status = self.request.GET.get('read_status', '')
        if read_status:
            is_read = read_status.lower() == 'read'
            queryset = queryset.filter(read=is_read)
            
        return queryset

class NotificationDetailView(LoginRequiredMixin, BaseAccountView, DetailView):
    """Class-based view to see notification details"""
    model = Notification
    template_name = 'notifications_detail.html'
    context_object_name = 'notification'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        notification = self.get_object()
        context.update({
            "page_title": notification.title,
            "page_description": "Notification details."
        })
        return context
    
    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)
    
    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        # Mark as read if not already
        if not obj.read:
            obj.mark_as_read()
        return obj

class NotificationRedirectView(LoginRequiredMixin, View):
    """Class-based view to redirect to notification action URL and mark as read"""
    def get(self, request, *args, **kwargs):
        notification = get_object_or_404(Notification, pk=kwargs.get('pk'), recipient=request.user)
        
        # Mark as read
        if not notification.read:
            notification.mark_as_read()
        
        # Redirect to action URL if available
        action_url = notification.get_action_url()
        if action_url:
            return HttpResponseRedirect(action_url)
        
        # Otherwise redirect to notification detail
        return redirect('account:notification_detail', pk=notification.pk)

class NotificationMarkReadView(LoginRequiredMixin, View):
    """Class-based view to mark notification as read via AJAX"""
    def post(self, request, *args, **kwargs):
        success = NotificationService.mark_as_read(kwargs.get('pk'), request.user)
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': success})
        
        # Non-AJAX fallback
        if success:
            messages.success(request, "Notification marked as read")
        else:
            messages.error(request, "Could not mark notification as read")
        
        return redirect('account:notification_list')

class NotificationMarkAllReadView(LoginRequiredMixin, View):
    """Class-based view to mark all notifications as read"""
    def post(self, request, *args, **kwargs):
        count = NotificationService.mark_all_as_read(request.user)
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'count': count})
        
        # Non-AJAX fallback
        messages.success(request, f"{count} notifications marked as read")
        return redirect('account:notification_list')

class NotificationDeleteView(LoginRequiredMixin, View):
    """Class-based view to delete a notification"""
    def post(self, request, *args, **kwargs):
        success = NotificationService.delete_notification(kwargs.get('pk'), request.user)
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': success})
        
        # Non-AJAX fallback
        if success:
            messages.success(request, "Notification deleted")
        else:
            messages.error(request, "Could not delete notification")
        
        return redirect('account:notification_list')

class NotificationCountView(LoginRequiredMixin, View):
    """Class-based API view to get unread notification count"""
    def get(self, request, *args, **kwargs):
        count = NotificationService.get_unread_count(request.user)
        return JsonResponse({'count': count})

# Security and Preferences Views
class SecuritySettingsView(LoginRequiredMixin, BaseAccountView):
    """View for managing security settings"""
    template_name = 'security_settings.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "page_title": "Security Settings",
            "page_description": "Manage your account security preferences.",
            "active_menu": "account",
            "active_submenu": "security",
        })
        return context
    
    def post(self, request, *args, **kwargs):
        action = request.POST.get('action')
        
        if action == 'change_password':
            current_password = request.POST.get('current_password')
            new_password = request.POST.get('new_password')
            confirm_password = request.POST.get('confirm_password')
            
            # Validation
            if not request.user.check_password(current_password):
                messages.error(request, "Current password is incorrect.")
                return redirect('account:security_settings')
            
            if new_password != confirm_password:
                messages.error(request, "New passwords do not match.")
                return redirect('account:security_settings')
            
            if len(new_password) < 8:
                messages.error(request, "Password must be at least 8 characters long.")
                return redirect('account:security_settings')
            
            # Update password
            request.user.set_password(new_password)
            request.user.save()
            
            # Send email notification
            self.send_password_change_email(request.user)
            
            messages.success(request, "Password changed successfully.")
            # Re-authenticate user after password change
            user = authenticate(username=request.user.username, password=new_password)
            login(request, user)
            
        return redirect('account:security_settings')
    
    def send_password_change_email(self, user):
        """Send email notification about password change"""
        context = {
            'user': user,
            'site_name': 'xLearning',
            'change_time': timezone.now(),
        }
        
        html_message = render_to_string('email/password_changed.html', context)
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject='Your Password Has Been Changed',
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=True
        )


class PreferencesView(LoginRequiredMixin, BaseAccountView):
    """View for managing user preferences"""
    template_name = 'preferences.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "page_title": "User Preferences",
            "page_description": "Customize your account settings and preferences."
        })
        return context
    
    def post(self, request, *args, **kwargs):
        # Handle preference updates
        # Example: language preference, notification settings, etc.
        messages.success(request, "Preferences updated successfully.")
        return self.get(request, *args, **kwargs)

# Admin user management views
class UserListView(LoginRequiredMixin, AdminRequiredMixin, BaseAccountView, ListView):
    """View for listing all users with filtering options"""
    model = CustomUser
    template_name = 'user_list.html'
    context_object_name = 'users'
    paginate_by = 10
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "page_title": "User Management",
            "page_description": "Manage all users in the system.",
            "user_types": UserType.choices,
            "selected_type": self.request.GET.get('type', ''),
            "search_query": self.request.GET.get('search', '')
        })
        return context
    
    def get_queryset(self):
        queryset = CustomUser.objects.all().order_by('-date_joined')
        
        # Filter by search query
        search_query = self.request.GET.get('search', '')
        if search_query:
            queryset = queryset.filter(
                Q(username__icontains=search_query) | 
                Q(email__icontains=search_query) |
                Q(first_name__icontains=search_query) |
                Q(last_name__icontains=search_query)
            )
        
        # Filter by user type
        user_type = self.request.GET.get('type', '')
        if user_type in [UserType.TEACHER, UserType.STUDENT, UserType.ADMIN]:
            queryset = queryset.filter(user_type=user_type)
            
        return queryset

class UserCreateView(LoginRequiredMixin, AdminRequiredMixin, TemplateLayoutMixin, CreateView):
    """View for creating a new user"""
    model = CustomUser
    template_name = 'user_form.html'
    fields = ['username', 'email', 'first_name', 'last_name', 'user_type', 'is_active']
    success_url = reverse_lazy('account:user_list')
    
    def form_valid(self, form):
        user = form.save(commit=False)
        # Set a default password
        default_password = 'changeme123'
        user.set_password(default_password)
        user.save()
        
        messages.success(self.request, f"User {user.username} created successfully. Default password: {default_password}")
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Create New User'
        context['submit_text'] = 'Create User'
        return context


class UserDetailView(LoginRequiredMixin, AdminRequiredMixin, TemplateLayoutMixin, DetailView):
    """View for viewing user details"""
    model = CustomUser
    template_name = 'user_detail.html'
    context_object_name = 'user_obj'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.get_object()
        context['profile'] = user.profile
        context['user_roles'] = user.user_roles.all()
        return context


class UserEditView(LoginRequiredMixin, AdminRequiredMixin, TemplateLayoutMixin, UpdateView):
    """View for editing a user"""
    model = CustomUser
    template_name = 'user_form.html'
    fields = ['username', 'email', 'first_name', 'last_name', 'user_type', 'is_active']
    context_object_name = 'user_obj'
    
    def get_success_url(self):
        return reverse_lazy('account:user_detail', kwargs={'pk': self.object.pk})
    
    def form_valid(self, form):
        messages.success(self.request, f"User {self.object.username} updated successfully.")
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Edit User: {self.object.username}'
        context['submit_text'] = 'Update User'
        return context


class UserDeleteView(LoginRequiredMixin, AdminRequiredMixin, TemplateLayoutMixin, DeleteView):
    """View for deleting a user"""
    model = CustomUser
    template_name = 'user_confirm_delete.html'
    success_url = reverse_lazy('account:user_list')
    context_object_name = 'user_obj'
    
    def delete(self, request, *args, **kwargs):
        user = self.get_object()
        messages.success(request, f"User {user.username} deleted successfully.")
        return super().delete(request, *args, **kwargs)


# instructor
class CreateInstructorView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Admin-only view to create instructor accounts"""
    model = CustomUser
    template_name = 'create_instructor.html'
    fields = ['username', 'email', 'first_name', 'last_name']
    success_url = reverse_lazy('account:user_list')
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.has_perm('account.can_manage_instructors')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'title': 'Create Instructor Account',
            'submit_text': 'Create Instructor',
            'active_menu': 'administration',
            'active_submenu': 'user_management',
        })
        return context
    
    def form_valid(self, form):
        user = form.save(commit=False)
        # Generate a random password
        password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
        user.set_password(password)
        user.user_type = UserType.TEACHER
        user.is_verified = True  # Instructors don't need email verification
        user.created_by_admin = True
        user.save()
        
        # Send email with login credentials
        self.send_instructor_welcome_email(user, password)
        
        messages.success(self.request, f"Instructor account created for {user.username}")
        return super().form_valid(form)
    
    def send_instructor_welcome_email(self, user, password):
        """Send welcome email with login credentials to instructor"""
        context = {
            'user': user,
            'password': password,
            'login_url': self.request.build_absolute_uri(reverse('account:login')),
            'site_name': 'xLearning',
        }
        
        html_message = render_to_string('email/instructor_welcome.html', context)
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject='Welcome to xLearning - Instructor Account Created',
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False
        )

class ApproveInstructorRequestView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Approve teacher requests from students"""
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.has_perm('account.can_manage_instructors')
    
    def post(self, request, *args, **kwargs):
        user_id = kwargs.get('user_id')
        user = get_object_or_404(CustomUser, id=user_id)
        
        if hasattr(user.profile, 'teacher_request_pending') and user.profile.teacher_request_pending:
            # Approve the request
            user.user_type = UserType.TEACHER
            user.instructor_approved_by = request.user
            user.save()
            
            # Clear pending request
            user.profile.teacher_request_pending = False
            user.profile.teacher_approved_date = timezone.now()
            user.profile.save()
            
            # Send approval email
            self.send_approval_email(user)
            
            messages.success(request, f"Instructor request approved for {user.username}")
        else:
            messages.error(request, "No pending instructor request found")
        
        return redirect('account:user_detail', pk=user_id)
    
    def send_approval_email(self, user):
        """Send approval email to new instructor"""
        context = {
            'user': user,
            'site_name': 'xLearning',
        }
        
        html_message = render_to_string('email/instructor_approved.html', context)
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject='Your Instructor Application Has Been Approved',
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=True
        )


# Role Management Views (already class-based, keeping them the same)
class RoleListView(LoginRequiredMixin, AdminRequiredMixin, TemplateLayoutMixin, ListView):
    """View for listing all roles"""
    model = Role
    template_name = 'role_list.html'
    context_object_name = 'roles'
    paginate_by = 10
    
    def get_queryset(self):
        queryset = Role.objects.all().order_by('name')
        
        # Filter by search query
        search_query = self.request.GET.get('search', '')
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) | 
                Q(description__icontains=search_query)
            )
            
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        return context


class RoleCreateView(LoginRequiredMixin, AdminRequiredMixin, TemplateLayoutMixin, CreateView):
    """View for creating a new role"""
    model = Role
    template_name = 'role_form.html'
    fields = ['name', 'description', 'permissions']
    success_url = reverse_lazy('account:role_list')
    
    def form_valid(self, form):
        messages.success(self.request, f"Role {form.instance.name} created successfully.")
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Create New Role'
        context['submit_text'] = 'Create Role'
        context['permissions'] = Permission.objects.all().order_by('content_type__app_label', 'content_type__model')
        return context


class RoleDetailView(LoginRequiredMixin, AdminRequiredMixin, TemplateLayoutMixin, DetailView):
    """View for viewing role details"""
    model = Role
    template_name = 'role_detail.html'
    context_object_name = 'role'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        role = self.get_object()
        context['role_permissions'] = role.permissions.all().order_by('content_type__app_label', 'content_type__model')
        context['users_with_role'] = UserRole.objects.filter(role=role).select_related('user')
        return context


class RoleEditView(LoginRequiredMixin, AdminRequiredMixin, TemplateLayoutMixin, UpdateView):
    """View for editing a role"""
    model = Role
    template_name = 'role_form.html'
    fields = ['name', 'description', 'permissions']
    context_object_name = 'role'
    
    def get_success_url(self):
        return reverse_lazy('account:role_detail', kwargs={'pk': self.object.pk})
    
    def form_valid(self, form):
        messages.success(self.request, f"Role {self.object.name} updated successfully.")
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Edit Role: {self.object.name}'
        context['submit_text'] = 'Update Role'
        context['permissions'] = Permission.objects.all().order_by('content_type__app_label', 'content_type__model')
        return context


class UserRoleRemoveView(LoginRequiredMixin, AdminRequiredMixin, TemplateLayoutMixin, DetailView):
    """View for removing a role from a user"""
    model = CustomUser
    template_name = 'user_role_remove.html'
    context_object_name = 'user_obj'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.get_object()
        role_id = self.kwargs.get('role_id')
        context['role'] = get_object_or_404(Role, pk=role_id)
        return context
    
    def post(self, request, *args, **kwargs):
        user = self.get_object()
        role_id = self.kwargs.get('role_id')
        
        try:
            user_role = UserRole.objects.get(user=user, role_id=role_id)
            role_name = user_role.role.name
            user_role.delete()
            messages.success(request, f"Role '{role_name}' removed from {user.username} successfully.")
        except UserRole.DoesNotExist:
            messages.error(request, "User does not have this role.")
        except Exception as e:
            messages.error(request, f"Error removing role: {str(e)}")
        
        return redirect('account:user_roles', pk=user.pk)

class RoleDeleteView(LoginRequiredMixin, AdminRequiredMixin, TemplateLayoutMixin, DeleteView):
    """View for deleting a role"""
    model = Role
    template_name = 'role_confirm_delete.html'
    success_url = reverse_lazy('account:role_list')
    context_object_name = 'role'
    
    def delete(self, request, *args, **kwargs):
        role = self.get_object()
        messages.success(request, f"Role {role.name} deleted successfully.")
        return super().delete(request, *args, **kwargs)


# Permission Management Views (already class-based, keeping them the same)
class PermissionListView(LoginRequiredMixin, AdminRequiredMixin, TemplateLayoutMixin, ListView):
    """View for listing all permissions"""
    model = Permission
    template_name = 'permission_list.html'
    context_object_name = 'permissions'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Permission.objects.all().order_by('content_type__app_label', 'content_type__model', 'name')
        
        # Filter by search query
        search_query = self.request.GET.get('search', '')
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) | 
                Q(codename__icontains=search_query) |
                Q(content_type__app_label__icontains=search_query) |
                Q(content_type__model__icontains=search_query)
            )
            
        # Filter by app
        app_filter = self.request.GET.get('app', '')
        if app_filter:
            queryset = queryset.filter(content_type__app_label=app_filter)
            
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        context['app_filter'] = self.request.GET.get('app', '')
        
        # Get unique app labels for filtering
        app_labels = Permission.objects.values_list('content_type__app_label', flat=True).distinct().order_by('content_type__app_label')
        context['app_labels'] = app_labels
        
        return context


# User Roles Views (already class-based, keeping them the same)
class UserRolesView(LoginRequiredMixin, AdminRequiredMixin, TemplateLayoutMixin, DetailView):
    """View for managing user roles"""
    model = CustomUser
    template_name = 'user_roles.html'
    context_object_name = 'user_obj'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.get_object()
        context['user_roles'] = UserRole.objects.filter(user=user).select_related('role')
        context['available_roles'] = Role.objects.exclude(id__in=UserRole.objects.filter(user=user).values_list('role_id', flat=True))
        return context


class UserRoleAddView(LoginRequiredMixin, AdminRequiredMixin, TemplateLayoutMixin, UpdateView):
    """View for adding a role to a user"""
    model = CustomUser
    template_name = 'user_role_add.html'
    fields = []
    
    def get_success_url(self):
        return reverse_lazy('account:user_roles', kwargs={'pk': self.object.pk})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.get_object()
        context['user_obj'] = user
        context['available_roles'] = Role.objects.exclude(id__in=UserRole.objects.filter(user=user).values_list('role_id', flat=True))
        return context
    
    def post(self, request, *args, **kwargs):
        user = self.get_object()
        role_id = request.POST.get('role_id')
        
        if role_id:
            try:
                role = Role.objects.get(pk=role_id)
                UserRole.objects.create(
                    user=user,
                    role=role,
                    assigned_by=request.user
                )
                messages.success(request, f"Role '{role.name}' assigned to {user.username} successfully.")
            except Role.DoesNotExist:
                messages.error(request, "Selected role does not exist.")
            except Exception as e:
                messages.error(request, f"Error assigning role: {str(e)}")
        
        return redirect('account:user_roles', pk=user.pk)
    

# User Settings Views
class SecuritySettingsView(LoginRequiredMixin, TemplateLayoutMixin, TemplateView):
    """View for managing security settings"""
    template_name = 'security_settings.html'
    
    def post(self, request, *args, **kwargs):
        action = request.POST.get('action')
        
        if action == 'change_password':
            current_password = request.POST.get('current_password')
            new_password = request.POST.get('new_password')
            confirm_password = request.POST.get('confirm_password')
            
            # Check current password
            if not request.user.check_password(current_password):
                messages.error(request, "Current password is incorrect.")
                return self.get(request, *args, **kwargs)
            
            # Check passwords match
            if new_password != confirm_password:
                messages.error(request, "New passwords do not match.")
                return self.get(request, *args, **kwargs)
            
            # Update password
            request.user.set_password(new_password)
            request.user.save()
            
            messages.success(request, "Password changed successfully.")
            # Re-authenticate user after password change
            user = authenticate(username=request.user.username, password=new_password)
            login(request, user)
            
        return self.get(request, *args, **kwargs)


class PreferencesView(LoginRequiredMixin, TemplateView):
    """View for managing user preferences"""
    template_name = 'preferences.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add any user preferences to context
        return context
    
    def post(self, request, *args, **kwargs):
        # Handle preference updates
        # Example: language preference, notification settings, etc.
        messages.success(request, "Preferences updated successfully.")
        return self.get(request, *args, **kwargs)


# account settings
class AccountSettingsView(LoginRequiredMixin, BaseAccountView):
    """Unified account settings page"""
    template_name = 'account_settings.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get user profile
        profile = self.request.user.profile
        
        # Get notification count
        unread_notifications = Notification.objects.filter(
            recipient=self.request.user,
            read=False
        ).count()
        
        # Get credit balance for students
        credit_balance = 0
        if hasattr(self.request.user, 'is_student') and self.request.user.is_student():
            credit_balance = self.get_credit_balance(self.request.user)
        
        context.update({
            "page_title": "Account Settings",
            "page_description": "Manage your account settings and preferences.",
            "active_menu": "account",
            "active_submenu": "settings",
            "profile": profile,
            "unread_notifications": unread_notifications,
            "credit_balance": credit_balance,
        })
        return context
    
    def get_credit_balance(self, user):
        """Calculate user's current credit balance"""
        from booking.models import CreditTransaction
        transactions = CreditTransaction.objects.filter(student=user)
        
        # Calculate credits from purchases and refunds
        credits = transactions.filter(
            transaction_type__in=['purchase', 'refund', 'bonus']
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        
        # Calculate debits from deductions
        debits = transactions.filter(
            transaction_type='deduction'
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        
        return credits - debits




class LicenseView(TemplateView):
    """View for license information"""
    template_name = 'license.html'
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        # Set consistent layout properties
        context.update({
            "layout": "front",
            "layout_path": context['theme'].set_layout("layout_front.html", context),
            "active_url": self.request.path,
            "is_front": True,
            "page_title": "License Information",
            "page_description": "License information for xLearning platform and its components.",
        })
        
        return context

class MoreThemesView(TemplateView):
    """View for more themes"""
    template_name = 'more_themes.html'
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        # Set consistent layout properties
        context.update({
            "layout": "front",
            "layout_path": context['theme'].set_layout("layout_front.html", context),
            "active_url": self.request.path,
            "is_front": True,
            "page_title": "More Themes",
            "page_description": "Explore additional themes and visual options for your xLearning experience.",
        })
        
        return context

class DocumentationView(TemplateView):
    """View for documentation"""
    template_name = 'documentation.html'
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        # Set consistent layout properties
        context.update({
            "layout": "front",
            "layout_path": context['theme'].set_layout("layout_front.html", context),
            "active_url": self.request.path,
            "is_front": True,
            "page_title": "Documentation",
            "page_description": "Comprehensive documentation and guides for using the xLearning platform.",
        })
        
        return context

class SupportView(TemplateView):
    """View for support"""
    template_name = 'support.html'
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        # Set consistent layout properties
        context.update({
            "layout": "front",
            "layout_path": context['theme'].set_layout("layout_front.html", context),
            "active_url": self.request.path,
            "is_front": True,
            "page_title": "Support",
            "page_description": "Get help and support for your xLearning experience.",
        })
        
        return context        