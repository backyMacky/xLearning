from django.http import JsonResponse, HttpResponseRedirect
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView, FormView, View
from django.contrib.auth.models import User, Permission
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

import uuid
import datetime

from apps.account.services import NotificationService
from .models import Notification, NotificationType, Role, UserRole, Profile, UserType

# Base Mixins
class SuperUserAccessMixin(UserPassesTestMixin):
    """Mixin to ensure superusers can access everything"""
    def test_func(self):
        return self.request.user.is_superuser

class AdminRequiredMixin(UserPassesTestMixin):
    """Mixin to ensure only admin users can access view"""
    def test_func(self):
        return self.request.user.is_authenticated and (self.request.user.is_admin or self.request.user.is_superuser)

class TemplateLayoutMixin:
    """Mixin to initialize template context with TemplateLayout"""
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from web_project import TemplateLayout
        context = TemplateLayout.init(self, context)
        return context

# Authentication Views
class RegisterView(TemplateLayoutMixin, FormView):
    """Class-based view for user registration"""
    template_name = 'register.html'
    success_url = reverse_lazy('account:verify_email')
    
    def get_form(self, form_class=None):
        # Django forms would be better here, but keeping close to original code
        return None
    
    def post(self, request, *args, **kwargs):
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        # Check if user already exists
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists")
            return redirect('account:register')
        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already exists")
            return redirect('account:register')
        
        # Create user
        user = User.objects.create_user(username=username, email=email, password=password)
        
        # Set user type (teacher or student)
        user_type = request.POST.get('user_type', UserType.STUDENT)
        user.user_type = user_type
        
        # Generate verification token
        token = str(uuid.uuid4())
        user.verification_token = token
        user.save()
        
        # Update profile
        profile = user.profile
        profile.native_language = request.POST.get('native_language')
        profile.learning_language = request.POST.get('learning_language')
        profile.save()
        
        # Send verification email
        self.send_verification_email(request, user, token)
        
        # Create success message
        messages.success(request, "Registration successful! Please check your email to verify your account.")
        
        # Redirect to verification page
        return redirect(self.success_url)
    
    def send_verification_email(self, request, user, token):
        """Helper method to send verification email"""
        verify_url = request.build_absolute_uri(
            reverse('account:verify_email_confirm', kwargs={'token': token})
        )
        
        subject = 'Verify your email address'
        message = f'Hi {user.username},\n\nPlease click the link below to verify your email address:\n\n{verify_url}\n\nThanks!'
        email_from = settings.DEFAULT_FROM_EMAIL
        recipient_list = [user.email]
        
        send_mail(subject, message, email_from, recipient_list)


class LoginView(TemplateLayoutMixin, FormView):
    """Class-based view for user login"""
    template_name = 'login.html'
    
    def get_form(self, form_class=None):
        # Django forms would be better here, but keeping close to original code
        return None
    
    def post(self, request, *args, **kwargs):
        email_username = request.POST.get('email-username')
        password = request.POST.get('password')
        next_url = request.POST.get('next', 'dashboards:overview')
        
        # Try to authenticate with email or username
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
                # Commented out email verification check
                # if not user.is_verified and user.user_type != UserType.ADMIN:
                #     messages.warning(request, "Please verify your email address before logging in.")
                #     return redirect('account:verify_email')
                
                login(request, user)
                return redirect(next_url)
            else:
                user = None
        except User.DoesNotExist:
            pass
        
        if user is None:
            messages.error(request, "Invalid email/username or password")
            return render(request, 'login.html', self.get_context_data())
        
        return super().form_invalid(None)


class LogoutView(View):
    """Class-based view for user logout"""
    def get(self, request, *args, **kwargs):
        logout(request)
        return redirect('/')


class VerifyEmailView(TemplateLayoutMixin, TemplateView):
    """Class-based view to verify email address"""
    template_name = 'verify_email.html'
    
    def get(self, request, *args, **kwargs):
        token = kwargs.get('token')
        if token:
            try:
                user = User.objects.get(verification_token=token)
                user.is_verified = True
                user.verification_token = None
                user.save()
                messages.success(request, "Email verification successful! You can now log in.")
                return redirect('account:login')
            except User.DoesNotExist:
                messages.error(request, "Invalid verification token.")
        
        return super().get(request, *args, **kwargs)


class ResendVerificationEmailView(View):
    """Class-based view to resend verification email"""
    def post(self, request, *args, **kwargs):
        email = request.POST.get('email')
        try:
            user = User.objects.get(email=email)
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
        except User.DoesNotExist:
            messages.error(request, "No account found with that email address.")
        
        return redirect('account:verify_email')


class ForgotPasswordView(TemplateLayoutMixin, FormView):
    """Class-based view for password recovery"""
    template_name = 'forgot_password.html'
    success_url = reverse_lazy('account:login')
    
    def get_form(self, form_class=None):
        # Django forms would be better here, but keeping close to original code
        return None
    
    def post(self, request, *args, **kwargs):
        email = request.POST.get('email')
        try:
            user = User.objects.get(email=email)
            
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
        except User.DoesNotExist:
            messages.error(request, "Email not found in our system")
            return self.render_to_response(self.get_context_data())


class ResetPasswordView(TemplateLayoutMixin, FormView):
    """Class-based view for resetting password with token validation"""
    template_name = 'reset_password.html'
    success_url = reverse_lazy('account:login')
    
    def get_form(self, form_class=None):
        # Django forms would be better here, but keeping close to original code
        return None
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['token'] = self.kwargs.get('token')
        return context
    
    def get(self, request, *args, **kwargs):
        token = kwargs.get('token')
        try:
            user = User.objects.get(reset_password_token=token)
            
            # Check if token has expired
            if user.reset_password_expiry < timezone.now():
                messages.error(request, "Password reset link has expired. Please request a new one.")
                return redirect('account:forgot_password')
                
        except User.DoesNotExist:
            messages.error(request, "Invalid password reset link.")
            return redirect('account:forgot_password')
            
        return super().get(request, *args, **kwargs)
    
    def post(self, request, *args, **kwargs):
        token = kwargs.get('token')
        try:
            user = User.objects.get(reset_password_token=token)
            
            # Check if token has expired
            if user.reset_password_expiry < timezone.now():
                messages.error(request, "Password reset link has expired. Please request a new one.")
                return redirect('account:forgot_password')
            
            password = request.POST.get('password')
            confirm_password = request.POST.get('confirm-password')
            
            if password != confirm_password:
                messages.error(request, "Passwords do not match.")
                return self.render_to_response(self.get_context_data())
            
            # Set new password
            user.set_password(password)
            user.reset_password_token = None
            user.reset_password_expiry = None
            user.save()
            
            messages.success(request, "Password has been reset successfully! You can now log in.")
            return redirect(self.success_url)
            
        except User.DoesNotExist:
            messages.error(request, "Invalid password reset link.")
            return redirect('account:forgot_password')


# Profile Views
class ProfileView(LoginRequiredMixin, TemplateLayoutMixin, DetailView):
    """Class-based view for viewing user profile"""
    model = User
    template_name = 'profile.html'
    context_object_name = 'profile_user'
    
    def get_object(self, queryset=None):
        username = self.kwargs.get('username')
        if username:
            return get_object_or_404(User, username=username)
        return self.request.user


class UpdateProfileView(LoginRequiredMixin, TemplateLayoutMixin, UpdateView):
    """Class-based view for updating user profile"""
    model = Profile
    template_name = 'edit_profile.html'
    fields = ['native_language', 'learning_language', 'bio', 'phone_number', 'date_of_birth', 'profile_image']
    success_url = reverse_lazy('account:profile')
    
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


# Notification Views
class NotificationListView(LoginRequiredMixin, TemplateLayoutMixin, ListView):
    """Class-based view to list user notifications"""
    model = Notification
    template_name = 'notification_list.html'
    context_object_name = 'notifications'
    paginate_by = 10
    
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
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['notification_types'] = NotificationType.choices
        context['selected_type'] = self.request.GET.get('type', '')
        context['selected_read_status'] = self.request.GET.get('read_status', '')
        context['unread_count'] = NotificationService.get_unread_count(self.request.user)
        return context


class NotificationDetailView(LoginRequiredMixin, TemplateLayoutMixin, DetailView):
    """Class-based view to see notification details"""
    model = Notification
    template_name = 'notifications_detail.html'
    context_object_name = 'notification'
    
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


# User Management Views (already class-based, keeping them the same)
class UserListView(LoginRequiredMixin, AdminRequiredMixin, TemplateLayoutMixin, ListView):
    """View for listing all users with filtering options"""
    model = User
    template_name = 'user_list.html'
    context_object_name = 'users'
    paginate_by = 10
    
    def get_queryset(self):
        queryset = User.objects.all().order_by('-date_joined')
        
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
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user_types'] = UserType.choices
        context['selected_type'] = self.request.GET.get('type', '')
        context['search_query'] = self.request.GET.get('search', '')
        return context


class UserCreateView(LoginRequiredMixin, AdminRequiredMixin, TemplateLayoutMixin, CreateView):
    """View for creating a new user"""
    model = User
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
    model = User
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
    model = User
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
    model = User
    template_name = 'user_confirm_delete.html'
    success_url = reverse_lazy('account:user_list')
    context_object_name = 'user_obj'
    
    def delete(self, request, *args, **kwargs):
        user = self.get_object()
        messages.success(request, f"User {user.username} deleted successfully.")
        return super().delete(request, *args, **kwargs)


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
    model = User
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
    model = User
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
    model = User
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


class PreferencesView(LoginRequiredMixin, TemplateLayoutMixin, TemplateView):
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