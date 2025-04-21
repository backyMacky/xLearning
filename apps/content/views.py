from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View, TemplateView, RedirectView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.http import Http404, JsonResponse
from django.contrib import messages
from django.db.models import Q, Count, Avg
from django.utils import timezone
from django.contrib.auth.models import User
from web_project import TemplateLayout
from web_project.template_helpers.theme import TemplateHelper

# Import models - adjust these based on your actual model structure
from .models import (
    Language, LanguageLevel, Course as Session,  # Rename the import for clarity
     Lesson, Resource, SessionAttendance, SessionFeedback, SessionReport
)
from .forms import (
    CourseForm as SessionForm,  
    CourseFilterForm as SessionFilterForm,
    ResourceFilterForm,
    ResourceForm  
)
# We'll also need access to booking models
from apps.booking.models import (
    Instructor, PrivateSessionSlot, GroupSession, 
    InstructorReview, InstructorSpecialty
)


class InstructorListView(ListView):
    """View to list all available instructors with filtering options"""
    model = Instructor
    context_object_name = 'instructors'
    template_name = 'instructor_list.html'
    paginate_by = 12
    
    def get_queryset(self):
        queryset = Instructor.objects.filter(is_available=True).select_related('user')
        
        # Get session type (private or group)
        session_type = self.request.GET.get('session_type', 'private')
        
        # Filter by language
        language_id = self.request.GET.get('language')
        if language_id:
            queryset = queryset.filter(teaching_languages__id=language_id)
        
        # Filter by level/specialty
        level_id = self.request.GET.get('level')
        if level_id:
            if session_type == 'group':
                # For group sessions, filter instructors who have group sessions at this level
                queryset = queryset.filter(group_sessions__level__id=level_id).distinct()
            else:
                # For private sessions, filter by levels they teach
                queryset = queryset.filter(
                    Q(private_slots__level__id=level_id) | 
                    Q(specialties__levels__id=level_id)
                ).distinct()
        
        # Search by name or keywords
        search_query = self.request.GET.get('q')
        if search_query:
            queryset = queryset.filter(
                Q(user__username__icontains=search_query) | 
                Q(bio__icontains=search_query) |
                Q(teaching_style__icontains=search_query)
            )
        
        # Add next available slot to each instructor
        now = timezone.now()
        for instructor in queryset:
            # Find the next available private session slot
            next_slot = PrivateSessionSlot.objects.filter(
                instructor=instructor,
                status='available',
                start_time__gt=now
            ).order_by('start_time').first()
            
            if next_slot:
                instructor.next_available_slot = next_slot.start_time
                instructor.next_available_slot_id = next_slot.id
            else:
                instructor.next_available_slot = None
                instructor.next_available_slot_id = None
                
            # Add languages as a property
            instructor.languages = instructor.teaching_languages.all()
            
            # Add instructor's rating
            instructor.rating = instructor.rating
            instructor.review_count = instructor.review_count
            
            # Add instructor's specialties
            instructor.specialties_list = instructor.specialties.all()
        
        return queryset
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        # Get group sessions if viewing group sessions tab
        session_type = self.request.GET.get('session_type', 'private')
        if session_type == 'group':
            context['group_sessions'] = GroupSession.objects.filter(
                status='scheduled',
                start_time__gt=timezone.now()
            ).select_related('instructor', 'language', 'level', 'instructor__user').order_by('start_time')
            
            # Mark sessions that current user is enrolled in
            if self.request.user.is_authenticated:
                user_sessions = self.request.user.enrolled_group_sessions.all()
                for session in context['group_sessions']:
                    session.is_enrolled = session in user_sessions
                    session.is_full = session.is_full
        
        # Add languages and levels for filtering
        context['languages'] = Language.objects.filter(is_active=True)
        context['levels'] = LanguageLevel.objects.all()
        
        # Set selected filter values
        context['selected_language'] = self.request.GET.get('language', '')
        context['selected_level'] = self.request.GET.get('level', '')
        
        # Add featured instructors
        context['featured_instructors'] = Instructor.objects.filter(
            is_featured=True, 
            is_available=True
        ).select_related('user')[:4]
        
        # Set active menu attributes
        context['active_menu'] = 'content'
        context['active_submenu'] = 'instructors'
        
        # Set the layout path using TemplateHelper
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context


class InstructorDetailView(DetailView):
    """View to display instructor profile and available booking slots"""
    model = Instructor
    context_object_name = 'instructor'
    template_name = 'instructor_detail.html'
    slug_field = 'user__username'
    slug_url_kwarg = 'username'
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        instructor = self.get_object()
        
        # Get available private session slots
        now = timezone.now()
        context['available_slots'] = PrivateSessionSlot.objects.filter(
            instructor=instructor,
            status='available',
            start_time__gt=now
        ).order_by('start_time')
        
        # Get available slots filtered by today's date
        today = now.date()
        context['available_slots_filtered'] = context['available_slots'].filter(
            start_time__date=today
        )
        
        # Add today's date for the calendar
        context['today'] = today
        
        # Get upcoming group sessions by this instructor
        context['group_sessions'] = GroupSession.objects.filter(
            instructor=instructor,
            status='scheduled',
            start_time__gt=now
        ).order_by('start_time')
        
        # Mark group sessions the user is enrolled in
        if self.request.user.is_authenticated:
            user_sessions = self.request.user.enrolled_group_sessions.all()
            for session in context['group_sessions']:
                session.is_enrolled = session in user_sessions
                session.is_full = session.is_full
                session.enrollment_percentage = session.enrollment_percentage
        
        # Get instructor reviews
        context['reviews'] = InstructorReview.objects.filter(
            instructor=instructor
        ).select_related('student').order_by('-created_at')[:3]
        context['review_count'] = InstructorReview.objects.filter(instructor=instructor).count()
        
        # Get instructor qualifications and experience
        context['qualifications'] = instructor.qualifications.all()
        context['experience'] = instructor.experiences.all()
        
        # Add bio and teaching style
        context['bio'] = instructor.bio
        context['teaching_style'] = instructor.teaching_style
        
        # Add language and specialties
        context['languages'] = instructor.teaching_languages.all()
        context['specialties'] = instructor.specialties.all()
        
        # Set active menu attributes
        context['active_menu'] = 'content'
        context['active_submenu'] = 'instructors'
        
        # Set the layout path using TemplateHelper
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context

class InstructorReviewsView(DetailView):
    """View to display all reviews for an instructor"""
    model = Instructor
    context_object_name = 'instructor'
    template_name = 'instructor_reviews.html'
    slug_field = 'user__username'
    slug_url_kwarg = 'username'
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        instructor = self.get_object()
        
        context['reviews'] = InstructorReview.objects.filter(
            instructor=instructor
        ).select_related('student').order_by('-created_at')
        
        # Set active menu attributes
        context['active_menu'] = 'content'
        context['active_submenu'] = 'instructors'
        
        # Set the layout path using TemplateHelper
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context


class GroupSessionListView(ListView):
    """View to list all upcoming group sessions"""
    model = GroupSession
    context_object_name = 'group_sessions'
    template_name = 'group_session_list.html'
    paginate_by = 12
    
    def get_queryset(self):
        now = timezone.now()
        queryset = GroupSession.objects.filter(
            status='scheduled',
            start_time__gt=now
        ).select_related('instructor', 'language', 'level', 'instructor__user').order_by('start_time')
        
        # Filter by language
        language_id = self.request.GET.get('language')
        if language_id:
            queryset = queryset.filter(language_id=language_id)
        
        # Filter by level
        level_id = self.request.GET.get('level')
        if level_id:
            queryset = queryset.filter(level_id=level_id)
        
        # Search by title or description
        search_query = self.request.GET.get('q')
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query) | 
                Q(description__icontains=search_query)
            )
        
        # Mark sessions the user is enrolled in
        if self.request.user.is_authenticated:
            user_sessions = self.request.user.enrolled_group_sessions.all()
            for session in queryset:
                session.is_enrolled = session in user_sessions
                session.is_full = session.is_full
        
        return queryset
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        # Get languages and levels for filtering
        context['languages'] = Language.objects.filter(is_active=True)
        context['levels'] = LanguageLevel.objects.all()
        
        # Set filter form with initial values
        context['filter_form'] = SessionFilterForm(self.request.GET)
        
        # Set active menu attributes
        context['active_menu'] = 'content'
        context['active_submenu'] = 'group_sessions'
        
        # Set the layout path using TemplateHelper
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context


class GroupSessionDetailView(DetailView):
    """View to display details of a group session and handle enrollment"""
    model = GroupSession
    context_object_name = 'session'
    template_name = 'group_session_detail.html'
    pk_url_kwarg = 'session_id'
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        session = self.get_object()
        
        # Check if user is enrolled
        if self.request.user.is_authenticated:
            context['is_enrolled'] = session.students.filter(id=self.request.user.id).exists()
        
        # Get enrolled students
        context['enrolled_students'] = session.students.all()
        
        # Calculate available slots
        context['available_slots'] = session.max_students - session.students.count()
        
        # Get instructor information
        context['instructor'] = session.instructor
        
        # Get related sessions (same language/level)
        context['related_sessions'] = GroupSession.objects.filter(
            status='scheduled',
            language=session.language,
            level=session.level,
            start_time__gt=timezone.now()
        ).exclude(id=session.id).order_by('start_time')[:3]
        
        # Set active menu attributes
        context['active_menu'] = 'content'
        context['active_submenu'] = 'group_sessions'
        
        # Set the layout path using TemplateHelper
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context

class CreateInstructorProfileView(LoginRequiredMixin, CreateView):
    """View for users to create their instructor profile"""
    model = Instructor
    template_name = 'instructor_profile_form.html'
    fields = ['bio', 'profile_image', 'teaching_style', 'hourly_rate']
    success_url = reverse_lazy('content:instructor_dashboard')
    
    def form_valid(self, form):
        # Set the user for this instructor profile
        form.instance.user = self.request.user
        
        # Set default values
        form.instance.is_available = True
        
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        # Get languages for selection
        context['languages'] = Language.objects.filter(is_active=True)
        context['specialties'] = InstructorSpecialty.objects.all()
        
        # Set active menu attributes
        context['active_menu'] = 'content'
        context['active_submenu'] = 'instructor_profile'
        
        context['title'] = 'Create Your Instructor Profile'
        
        # Set the layout path using TemplateHelper
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context
    
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        
        # Handle many-to-many fields
        if hasattr(self, 'object') and self.object:
            # Add languages
            language_ids = request.POST.getlist('languages')
            if language_ids:
                self.object.teaching_languages.set(language_ids)
            
            # Add specialties
            specialty_ids = request.POST.getlist('specialties')
            if specialty_ids:
                self.object.specialties.set(specialty_ids)
        
        return response

class UpdateInstructorProfileView(LoginRequiredMixin, UpdateView):
    """View for instructors to update their profile"""
    model = Instructor
    template_name = 'instructor_profile_form.html'
    fields = ['bio', 'profile_image', 'teaching_style', 'hourly_rate', 'is_available']
    success_url = reverse_lazy('content:instructor_dashboard')
    
    def get_object(self, queryset=None):
        # Get the instructor profile for the current user
        return get_object_or_404(Instructor, user=self.request.user)
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        # Get languages and specialties for selection
        context['languages'] = Language.objects.filter(is_active=True)
        context['specialties'] = InstructorSpecialty.objects.all()
        
        # Set selected languages and specialties
        context['selected_languages'] = self.object.teaching_languages.values_list('id', flat=True)
        context['selected_specialties'] = self.object.specialties.values_list('id', flat=True)
        
        # Set active menu attributes
        context['active_menu'] = 'content'
        context['active_submenu'] = 'instructor_profile'
        
        context['title'] = 'Update Your Instructor Profile'
        
        # Set the layout path using TemplateHelper
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context
    
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        
        # Handle many-to-many fields
        if hasattr(self, 'object') and self.object:
            # Update languages
            language_ids = request.POST.getlist('languages')
            if language_ids:
                self.object.teaching_languages.set(language_ids)
            else:
                self.object.teaching_languages.clear()
            
            # Update specialties
            specialty_ids = request.POST.getlist('specialties')
            if specialty_ids:
                self.object.specialties.set(specialty_ids)
            else:
                self.object.specialties.clear()
        
        return response


class InstructorDashboardView(LoginRequiredMixin, TemplateView):
    """Dashboard for instructors to manage their sessions"""
    template_name = 'instructor_dashboard.html'
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        user = self.request.user
        
        # Check if the user has an instructor profile
        has_instructor_profile = hasattr(user, 'instructor_profile')
        context['has_instructor_profile'] = has_instructor_profile
        
        if has_instructor_profile:
            instructor = user.instructor_profile
            context['instructor'] = instructor
            
            # Current time
            now = timezone.now()
            context['now'] = now
            
            # Get analytics data
            analytics_data = self.get_instructor_dashboard_data(instructor)
            context.update(analytics_data)
            
            # Get available and booked slots for the calendar
            context['available_slots'] = PrivateSessionSlot.objects.filter(
                instructor=instructor,
                status='available',
                start_time__gt=now
            ).order_by('start_time')
            
            context['booked_slots'] = PrivateSessionSlot.objects.filter(
                instructor=instructor,
                status='booked',
                start_time__gt=now
            ).order_by('start_time')
            
            # Get upcoming group sessions
            context['upcoming_group_sessions'] = GroupSession.objects.filter(
                instructor=instructor,
                status='scheduled',
                start_time__gt=now
            ).order_by('start_time')
            
            # Get recent reviews
            context['recent_reviews'] = InstructorReview.objects.filter(
                instructor=instructor
            ).order_by('-created_at')[:5]
        
        # Set active menu attributes
        context['active_menu'] = 'instructor'
        context['active_submenu'] = 'instructor-dashboard'
        
        # Set the layout path using TemplateHelper
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context
    
    def get_instructor_dashboard_data(self, instructor):
        """Get analytics data for the instructor dashboard"""
        now = timezone.now()
        data = {}
        
        # Active sessions (currently happening)
        active_sessions = []
        active_private_sessions = PrivateSessionSlot.objects.filter(
            instructor=instructor,
            start_time__lte=now,
            end_time__gte=now,
            status__in=['booked', 'active']
        ).select_related('student', 'language', 'level')
        
        active_group_sessions = GroupSession.objects.filter(
            instructor=instructor,
            start_time__lte=now,
            end_time__gte=now,
            status__in=['scheduled', 'active']
        ).select_related('language', 'level')
        
        # Format active sessions for the template
        for session in active_private_sessions:
            active_sessions.append({
                'id': session.id,
                'is_private': True,
                'start_time': session.start_time,
                'end_time': session.end_time,
                'student': session.student,
                'meeting_link': session.meeting_link,
                'status': 'Active'
            })
        
        for session in active_group_sessions:
            active_sessions.append({
                'id': session.id,
                'is_private': False,
                'title': session.title,
                'start_time': session.start_time,
                'end_time': session.end_time,
                'students': session.students.all(),
                'students_count': session.students.count(),
                'max_students': session.max_students,
                'enrollment_percentage': session.enrollment_percentage,
                'meeting_link': session.meeting_link,
                'status': 'Active'
            })
        
        data['active_sessions'] = active_sessions
        
        # Upcoming sessions (scheduled for the future)
        upcoming_sessions = []
        upcoming_private_sessions = PrivateSessionSlot.objects.filter(
            instructor=instructor,
            start_time__gt=now,
            status__in=['available', 'booked']
        ).select_related('student', 'language', 'level')
        
        upcoming_group_sessions = GroupSession.objects.filter(
            instructor=instructor,
            start_time__gt=now,
            status='scheduled'
        ).select_related('language', 'level')
        
        # Format upcoming sessions for the template
        for session in upcoming_private_sessions:
            upcoming_sessions.append({
                'id': session.id,
                'is_private': True,
                'start_time': session.start_time,
                'end_time': session.end_time,
                'student': session.student,
                'language': session.language,
                'level': session.level,
                'status': session.status
            })
        
        for session in upcoming_group_sessions:
            upcoming_sessions.append({
                'id': session.id,
                'is_private': False,
                'title': session.title,
                'start_time': session.start_time,
                'end_time': session.end_time,
                'students': session.students.all(),
                'students_count': session.students.count(),
                'max_students': session.max_students,
                'language': session.language,
                'level': session.level,
                'status': session.status,
                'enrollment_percentage': session.enrollment_percentage
            })
        
        data['upcoming_sessions'] = upcoming_sessions
        
        # Past sessions (completed, cancelled, no-show)
        past_sessions = []
        past_private_sessions = PrivateSessionSlot.objects.filter(
            instructor=instructor,
            end_time__lt=now
        ).select_related('student').order_by('-start_time')[:10]
        
        past_group_sessions = GroupSession.objects.filter(
            instructor=instructor,
            end_time__lt=now
        ).order_by('-start_time')[:10]
        
        # Format past sessions for the template
        for session in past_private_sessions:
            past_sessions.append({
                'id': session.id,
                'is_private': True,
                'start_time': session.start_time,
                'end_time': session.end_time,
                'student': session.student,
                'status': session.status,
                'recording_url': getattr(session, 'recording_url', None)
            })
        
        for session in past_group_sessions:
            past_sessions.append({
                'id': session.id,
                'is_private': False,
                'title': session.title,
                'start_time': session.start_time,
                'end_time': session.end_time,
                'students': session.students.all(),
                'students_count': session.students.count(),
                'status': session.status,
                'recording_url': getattr(session, 'recording_url', None)
            })
        
        data['past_sessions'] = past_sessions
        
        # Analytics calculations
        total_sessions = PrivateSessionSlot.objects.filter(instructor=instructor).count() + \
                        GroupSession.objects.filter(instructor=instructor).count()
        
        completed_sessions = PrivateSessionSlot.objects.filter(
            instructor=instructor, 
            status='completed'
        ).count() + \
        GroupSession.objects.filter(
            instructor=instructor,
            status='completed'
        ).count()
        
        cancelled_sessions = PrivateSessionSlot.objects.filter(
            instructor=instructor, 
            status='cancelled'
        ).count() + \
        GroupSession.objects.filter(
            instructor=instructor,
            status='cancelled'
        ).count()
        
        # Calculate percentages
        completed_ratio = 0
        cancellation_ratio = 0
        if total_sessions > 0:
            completed_ratio = round((completed_sessions / total_sessions) * 100)
            cancellation_ratio = round((cancelled_sessions / total_sessions) * 100)
        
        # Total unique students
        student_ids = set()
        for session in PrivateSessionSlot.objects.filter(
            instructor=instructor,
            student__isnull=False
        ).values_list('student_id', flat=True):
            student_ids.add(session)
        
        for session in GroupSession.objects.filter(instructor=instructor):
            for student_id in session.students.values_list('id', flat=True):
                student_ids.add(student_id)
        
        total_students = len(student_ids)
        
        # Add these analytics to the data
        data['total_sessions'] = total_sessions
        data['completed_sessions'] = completed_sessions
        data['cancelled_sessions'] = cancelled_sessions
        data['completed_ratio'] = completed_ratio
        data['cancellation_ratio'] = cancellation_ratio
        data['total_students'] = total_students
        
        return data

    
class SessionForm(LoginRequiredMixin, UpdateView):
    """Base form for both private and group session slot creation/editing"""
    template_name = 'session_form.html'



class DeleteGroupSessionView(LoginRequiredMixin, DeleteView):
    """View for instructors to delete group sessions"""
    model = GroupSession
    template_name = 'session_confirm_delete.html'
    pk_url_kwarg = 'session_id'
    success_url = reverse_lazy('content:instructor_dashboard')
    
    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        # Check ownership
        if not hasattr(self.request.user, 'instructor_profile') or obj.instructor.user != self.request.user:
            messages.error(self.request, "You don't have permission to delete this session.")
            return redirect('content:instructor_dashboard')
        return obj
    
    def delete(self, request, *args, **kwargs):
        session = self.get_object()
        
        # If students are enrolled, we should notify them
        if session.students.exists():
            # Here you would add logic to notify students
            # For now, just show a message to the instructor
            messages.warning(request, f"There were {session.students.count()} students enrolled. They will be notified of the cancellation.")
        
        messages.success(request, "Group session deleted successfully.")
        return super().delete(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        context['title'] = 'Delete Group Session'
        context['is_private'] = False
        
        # Set active menu attributes
        context['active_menu'] = 'content'
        context['active_submenu'] = 'instructor_dashboard'
        
        # Set the layout path using TemplateHelper
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context


class StudentDashboardView(LoginRequiredMixin, TemplateView):
    """Dashboard for students to view their booked sessions"""
    template_name = 'student_dashboard.html'
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        user = self.request.user
        now = timezone.now()
        
        # Get student's private sessions
        context['upcoming_private_sessions'] = PrivateSessionSlot.objects.filter(
            student=user,
            status='booked',
            start_time__gt=now
        ).select_related('instructor', 'instructor__user', 'language', 'level').order_by('start_time')
        
        # Get past private sessions
        context['past_private_sessions'] = PrivateSessionSlot.objects.filter(
            student=user,
            start_time__lt=now
        ).select_related('instructor', 'instructor__user').order_by('-start_time')[:10]
        
        # Get enrolled group sessions
        context['upcoming_group_sessions'] = GroupSession.objects.filter(
            students=user,
            status='scheduled',
            start_time__gt=now
        ).select_related('instructor', 'instructor__user', 'language', 'level').order_by('start_time')
        
        # Get past group sessions
        context['past_group_sessions'] = GroupSession.objects.filter(
            students=user,
            start_time__lt=now
        ).select_related('instructor', 'instructor__user').order_by('-start_time')[:10]
        
        # Get credit balance
        credit_balance = 0
        from apps.booking.models import CreditTransaction
        if CreditTransaction.objects.filter(student=user).exists():
            last_transaction = CreditTransaction.objects.filter(student=user).latest('created_at')
            credit_balance = last_transaction.get_balance()
        context['credit_balance'] = credit_balance
        
        # Get instructors the student has booked with
        instructor_ids = list(PrivateSessionSlot.objects.filter(
            student=user
        ).values_list('instructor', flat=True).distinct())
        
        instructor_ids.extend(GroupSession.objects.filter(
            students=user
        ).values_list('instructor', flat=True).distinct())
        
        instructor_ids = set(instructor_ids)
        
        if instructor_ids:
            context['my_instructors'] = Instructor.objects.filter(
                id__in=instructor_ids
            ).select_related('user')
        
        # Get recommended instructors
        if context.get('my_instructors'):
            # Get languages student has studied
            language_ids = list(PrivateSessionSlot.objects.filter(
                student=user
            ).values_list('language', flat=True).distinct())
            
            language_ids.extend(GroupSession.objects.filter(
                students=user
            ).values_list('language', flat=True).distinct())
            
            language_ids = set(language_ids)
            
            # Get instructors who teach these languages but aren't in my_instructors
            if language_ids:
                context['recommended_instructors'] = Instructor.objects.filter(
                    teaching_languages__id__in=language_ids
                ).exclude(
                    id__in=[i.id for i in context.get('my_instructors', [])]
                ).select_related('user').distinct()[:4]
        
        # Set active menu attributes
        context['active_menu'] = 'booking'
        context['active_submenu'] = 'student_dashboard'
        
        # Set the layout path using TemplateHelper
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context



class CreateInstructorReviewView(LoginRequiredMixin, CreateView):
    """View for users to leave reviews for instructors"""
    model = InstructorReview
    template_name = 'create_review.html'
    fields = ['rating', 'comment']
    
    def get_success_url(self):
        return reverse('content:instructor_detail', kwargs={'username': self.instructor.user.username})
    
    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        
        # Get the instructor
        self.instructor = get_object_or_404(Instructor, id=kwargs.get('instructor_id'))
        
        # Get session information if provided
        session_type = kwargs.get('session_type')
        session_id = kwargs.get('session_id')
        
        self.private_session = None
        self.group_session = None
        
        if session_type == 'private' and session_id:
            self.private_session = get_object_or_404(
                PrivateSessionSlot, 
                id=session_id,
                student=request.user,
                instructor=self.instructor
            )
        elif session_type == 'group' and session_id:
            self.group_session = get_object_or_404(
                GroupSession,
                id=session_id,
                students=request.user,
                instructor=self.instructor
            )
    
    def form_valid(self, form):
        # Set the instructor and student
        form.instance.instructor = self.instructor
        form.instance.student = self.request.user
        
        # Link to the session if applicable
        if hasattr(self, 'private_session') and self.private_session:
            form.instance.private_session = self.private_session
        elif hasattr(self, 'group_session') and self.group_session:
            form.instance.group_session = self.group_session
        
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        context['instructor'] = self.instructor
        
        # Add session context if applicable
        if hasattr(self, 'private_session') and self.private_session:
            context['session'] = self.private_session
            context['session_type'] = 'private'
        elif hasattr(self, 'group_session') and self.group_session:
            context['session'] = self.group_session
            context['session_type'] = 'group'
        
        context['title'] = f'Review {self.instructor.user.username}'
        
        # Set active menu attributes
        context['active_menu'] = 'booking'
        context['active_submenu'] = 'student_dashboard'
        
        # Set the layout path using TemplateHelper
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context


# Compatibility API views for existing front-end components
def get_course_lessons(request, course_id):
    """API endpoint compatible with the original code to get lessons for a specific course/session"""
    # Map existing course_id to a new session model if needed
    session = get_object_or_404(Session, id=course_id)

    # Check permissions
    if not request.user.is_superuser:
        if request.user.is_teacher and session.teacher != request.user:
            return JsonResponse({'error': 'Permission denied'}, status=403)
        elif request.user.is_student and session not in request.user.enrolled_courses.all():
            return JsonResponse({'error': 'Permission denied'}, status=403)

    # Get all lessons from all modules in the course/session
    lessons = []
    for module in session.modules.all().order_by('order'):
        for lesson in module.lessons.all().order_by('order'):
            lessons.append({
                'id': lesson.id,
                'title': f"{module.title} - {lesson.title}",
                'module_id': module.id,
                'module_title': module.title,
            })

    return JsonResponse(lessons, safe=False)


def mark_lesson_complete(request, lesson_id):
    """API endpoint compatible with the original code to mark a lesson as complete/incomplete for a student"""
    if not request.user.is_student:
        return JsonResponse({'error': 'Only students can mark lessons'}, status=403)

    lesson = get_object_or_404(Lesson, id=lesson_id)
    course = lesson.module.course
    
    # Check if student is enrolled in the course/session
    if course not in request.user.enrolled_courses.all():
        return JsonResponse({'error': 'You are not enrolled in this session'}, status=403)
    
    # Get or create course/session progress
    from .models import CourseProgress, LessonCompletion
    progress, created = CourseProgress.objects.get_or_create(
        student=request.user,
        course=course
    )
    
    action = request.POST.get('action', 'complete')
    
    if action == 'complete':
        # Mark lesson as complete
        LessonCompletion.objects.get_or_create(
            student=request.user,
            lesson=lesson
        )
        return JsonResponse({'status': 'success', 'completed': True})
    else:
        # Mark lesson as incomplete
        LessonCompletion.objects.filter(
            student=request.user,
            lesson=lesson
        ).delete()
        return JsonResponse({'status': 'success', 'completed': False})


class CreatePrivateSessionSlotView(LoginRequiredMixin, CreateView):
    """View for instructors to create private session slots"""
    model = PrivateSessionSlot
    fields = ['start_time', 'duration_minutes', 'language', 'level']
    success_url = reverse_lazy('content:instructor_dashboard')
    template_name = 'session_form.html'
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Remove the default widgets and use flatpickr in the template
        # Let the template handle the datetime picker properly
        return form
    
    def form_valid(self, form):
        # Check if user has instructor profile
        if not hasattr(self.request.user, 'instructor_profile'):
            messages.error(self.request, "You need to create an instructor profile first.")
            return redirect('content:create_instructor_profile')
        
        # Set the instructor
        form.instance.instructor = self.request.user.instructor_profile
        
        # Set status to available
        form.instance.status = 'available'
        
        # Calculate end_time based on duration
        form.instance.end_time = form.instance.start_time + timezone.timedelta(minutes=form.instance.duration_minutes)
        
        # Set success message
        messages.success(self.request, "Private session slot created successfully!")
        
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        # Get languages and levels for selection
        context['languages'] = Language.objects.filter(is_active=True)
        context['levels'] = LanguageLevel.objects.all()
        
        context['title'] = 'Create Private Session Slot'
        context['is_private'] = True
        
        # Set active menu attributes
        context['active_menu'] = 'instructor'
        context['active_submenu'] = 'create-private-slot'
        
        # Set the layout path using TemplateHelper
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context
    
class UpdatePrivateSessionSlotView(LoginRequiredMixin, UpdateView):
    """View for instructors to update private session slots"""
    model = PrivateSessionSlot
    fields = ['start_time', 'duration_minutes', 'language', 'level']
    template_name = 'session_form.html'
    pk_url_kwarg = 'slot_id'
    success_url = reverse_lazy('content:instructor_dashboard')
    
    def get_queryset(self):
        # Ensure instructors can only edit their own slots
        return PrivateSessionSlot.objects.filter(
            instructor=self.request.user.instructor_profile,
            status='available'  # Only allow editing available slots
        )
    
    def form_valid(self, form):
        # Calculate end_time based on duration
        form.instance.end_time = form.instance.start_time + timezone.timedelta(minutes=form.instance.duration_minutes)
        
        # Set success message
        messages.success(self.request, "Private session slot updated successfully!")
        
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        # Get languages and levels for selection
        context['languages'] = Language.objects.filter(is_active=True)
        context['levels'] = LanguageLevel.objects.all()
        
        context['title'] = 'Update Private Session Slot'
        context['is_private'] = True
        context['is_update'] = True
        
        # Set active menu attributes
        context['active_menu'] = 'instructor'
        context['active_submenu'] = 'instructor-dashboard'
        
        # Set the layout path using TemplateHelper
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context


class DeletePrivateSessionSlotView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """View for instructors to delete private session slots"""
    model = PrivateSessionSlot
    template_name = 'session_confirm_delete.html'
    pk_url_kwarg = 'slot_id'
    success_url = reverse_lazy('content:instructor_dashboard')
    
    def test_func(self):
        # Check if the user is an instructor and owns this slot
        if not (hasattr(self.request.user, 'is_teacher') and self.request.user.is_teacher and hasattr(self.request.user, 'instructor_profile')):
            return False
        
        slot = self.get_object()
        return slot.instructor.user == self.request.user
    
    def delete(self, request, *args, **kwargs):
        slot = self.get_object()
        
        # Don't allow deleting if the slot is already booked
        if slot.status != 'available':
            messages.error(request, "Cannot delete a session that is already booked.")
            return redirect('content:instructor_dashboard')
        
        messages.success(request, "Session slot deleted successfully.")
        return super().delete(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        context['title'] = 'Delete Private Session Slot'
        context['is_private'] = True
        
        # Set active menu attributes
        context['active_menu'] = 'content'
        context['active_submenu'] = 'instructor_dashboard'
        
        # Set the layout path using TemplateHelper
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context


class CreateGroupSessionView(LoginRequiredMixin, CreateView):
    """View for instructors to create group sessions"""
    model = GroupSession
    fields = ['title', 'description', 'language', 'level', 'start_time', 
              'duration_minutes', 'max_students', 'price']
    success_url = reverse_lazy('content:instructor_dashboard')
    template_name = 'session_form.html'
    
    def form_valid(self, form):
        # Check if user has instructor profile
        if not hasattr(self.request.user, 'instructor_profile'):
            messages.error(self.request, "You need to create an instructor profile first.")
            return redirect('content:create_instructor_profile')
            
        # Set the instructor
        form.instance.instructor = self.request.user.instructor_profile
        
        # Set status to scheduled
        form.instance.status = 'scheduled'
        
        # Calculate end_time based on duration
        form.instance.end_time = form.instance.start_time + timezone.timedelta(minutes=form.instance.duration_minutes)
        
        # Set success message
        messages.success(self.request, "Group session created successfully!")
        
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        # Get languages and levels for selection
        context['languages'] = Language.objects.filter(is_active=True)
        context['levels'] = LanguageLevel.objects.all()
        
        context['title'] = 'Create Group Session'
        context['is_private'] = False
        
        # Set active menu attributes
        context['active_menu'] = 'instructor'
        context['active_submenu'] = 'create-group-session'
        
        # Set the layout path using TemplateHelper
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context

class UpdateGroupSessionView(LoginRequiredMixin, UpdateView):
    """View for instructors to update group sessions"""
    model = GroupSession
    fields = ['title', 'description', 'language', 'level', 'start_time', 
              'duration_minutes', 'max_students', 'price']
    template_name = 'session_form.html'
    pk_url_kwarg = 'session_id'
    success_url = reverse_lazy('content:instructor_dashboard')
    
    def get_queryset(self):
        # Ensure instructors can only edit their own sessions
        return GroupSession.objects.filter(
            instructor=self.request.user.instructor_profile,
            status='scheduled'  # Only allow editing scheduled sessions
        )
    
    def form_valid(self, form):
        # Don't allow reducing max_students below current enrollment
        if form.instance.max_students < self.object.students.count():
            form.instance.max_students = self.object.students.count()
            messages.warning(self.request, "Maximum students cannot be less than current enrollment.")
        
        # Calculate end_time based on duration
        form.instance.end_time = form.instance.start_time + timezone.timedelta(minutes=form.instance.duration_minutes)
        
        # Set success message
        messages.success(self.request, "Group session updated successfully!")
        
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        # Get languages and levels for selection
        context['languages'] = Language.objects.filter(is_active=True)
        context['levels'] = LanguageLevel.objects.all()
        
        context['title'] = 'Update Group Session'
        context['is_private'] = False
        context['is_update'] = True
        
        # Set active menu attributes
        context['active_menu'] = 'instructor'
        context['active_submenu'] = 'instructor-dashboard'
        
        # Set the layout path using TemplateHelper
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context
class RedirectToCourseListView(RedirectView):
    """Redirects from the old course list URL to the new instructor list"""
    
    def get_redirect_url(self, *args, **kwargs):
        # Get any query parameters from the request
        query_params = self.request.GET.urlencode()
        
        # Construct the redirect URL
        redirect_url = reverse('content:instructor_list')
        
        # Append query parameters if they exist
        if query_params:
            redirect_url = f"{redirect_url}?{query_params}"
            
        return redirect_url


class RedirectToCourseDetailView(RedirectView):
    """Redirects from old course detail URLs to instructor detail or group session detail"""
    
    def get_redirect_url(self, *args, **kwargs):
        # Get the course by slug
        slug = kwargs.get('slug')
        session = get_object_or_404(Session, slug=slug)
        
        # Check if this is a group session or private instructor session
        if hasattr(session, 'is_group_session') and session.is_group_session:
            # Redirect to group session detail
            return reverse('content:group_session_detail', kwargs={'session_id': session.id})
        else:
            # Redirect to instructor detail
            return reverse('content:instructor_detail', kwargs={'username': session.teacher.username})  



class ResourceListView(LoginRequiredMixin, ListView):
    """View to list educational resources with filtering options"""
    model = Resource
    context_object_name = 'resources'
    template_name = 'resource_list.html'
    paginate_by = 12
    
    def get_queryset(self):
        queryset = Resource.objects.all()
        
        # Filter by language
        language_id = self.request.GET.get('language')
        if language_id:
            queryset = queryset.filter(language_id=language_id)
        
        # Filter by level
        level_id = self.request.GET.get('level')
        if level_id:
            queryset = queryset.filter(level_id=level_id)
        
        # Filter by resource type
        resource_type = self.request.GET.get('resource_type')
        if resource_type:
            queryset = queryset.filter(resource_type=resource_type)
        
        # Search by title or description
        search_query = self.request.GET.get('q')
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query) | 
                Q(description__icontains=search_query)
            )
        
        # Show only public resources to regular users
        if not self.request.user.is_superuser and not self.request.user.is_teacher:
            queryset = queryset.filter(is_public=True)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        # Get languages and levels for filtering
        context['languages'] = Language.objects.filter(is_active=True)
        context['levels'] = LanguageLevel.objects.all()
        
        # Set filter form with initial values
        context['filter_form'] = ResourceFilterForm(self.request.GET)
        
        # Set active menu attributes
        context['active_menu'] = 'content'
        context['active_submenu'] = 'resources'
        
        # Set the layout path
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context

class CreateResourceView(LoginRequiredMixin, CreateView):
    """View for creating educational resources"""
    model = Resource
    form_class = ResourceForm
    template_name = 'resource_form.html'
    success_url = reverse_lazy('content:resource_list')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, "Resource created successfully!")
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        context['title'] = 'Create Educational Resource'
        context['submit_text'] = 'Create Resource'
        
        # Set active menu attributes
        context['active_menu'] = 'content'
        context['active_submenu'] = 'resources'
        
        # Set the layout path
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context

class UpdateResourceView(LoginRequiredMixin, UpdateView):
    """View for updating educational resources"""
    model = Resource
    form_class = ResourceForm
    template_name = 'resource_form.html'
    pk_url_kwarg = 'resource_id'
    success_url = reverse_lazy('content:resource_list')
    
    def get_queryset(self):
        # Users can only edit their own resources unless they're admins
        if self.request.user.is_superuser:
            return Resource.objects.all()
        return Resource.objects.filter(created_by=self.request.user)
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        messages.success(self.request, "Resource updated successfully!")
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        context['title'] = 'Edit Educational Resource'
        context['submit_text'] = 'Update Resource'
        
        # Set active menu attributes
        context['active_menu'] = 'content'
        context['active_submenu'] = 'resources'
        
        # Set the layout path
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context

class DeleteResourceView(LoginRequiredMixin, DeleteView):
    """View for deleting educational resources"""
    model = Resource
    template_name = 'resource_confirm_delete.html'
    pk_url_kwarg = 'resource_id'
    success_url = reverse_lazy('content:resource_list')
    
    def get_queryset(self):
        # Users can only delete their own resources unless they're admins
        if self.request.user.is_superuser:
            return Resource.objects.all()
        return Resource.objects.filter(created_by=self.request.user)
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, "Resource deleted successfully.")
        return super().delete(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        context['title'] = 'Delete Educational Resource'
        
        # Set active menu attributes
        context['active_menu'] = 'content'
        context['active_submenu'] = 'resources'
        
        # Set the layout path
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context     


class CreateSessionFeedbackView(LoginRequiredMixin, CreateView):
    """View for students to leave feedback after sessions"""
    model = SessionFeedback
    template_name = 'session_feedback_form.html'
    fields = ['rating', 'comment', 'teaching_quality', 'technical_quality', 'content_relevance']
    
    def get_success_url(self):
        if hasattr(self, 'private_session') and self.private_session:
            return reverse('content:student_dashboard')
        elif hasattr(self, 'group_session') and self.group_session:
            return reverse('content:group_session_detail', kwargs={'session_id': self.group_session.id})
        return reverse('content:student_dashboard')
    
    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        
        session_type = kwargs.get('session_type')
        session_id = kwargs.get('session_id')
        
        self.private_session = None
        self.group_session = None
        
        if session_type == 'private':
            self.private_session = get_object_or_404(
                PrivateSessionSlot, 
                id=session_id,
                student=request.user
            )
            self.instructor = self.private_session.instructor
        elif session_type == 'group':
            self.group_session = get_object_or_404(
                GroupSession,
                id=session_id
            )
            # Verify the user is enrolled
            if not self.group_session.students.filter(id=request.user.id).exists():
                raise Http404("You are not enrolled in this session")
            self.instructor = self.group_session.instructor
    
    def form_valid(self, form):
        # Set the session information
        form.instance.user = self.request.user
        
        if hasattr(self, 'private_session') and self.private_session:
            form.instance.session_type = 'private'
            form.instance.private_session = self.private_session
        elif hasattr(self, 'group_session') and self.group_session:
            form.instance.session_type = 'group'
            form.instance.group_session = self.group_session
        
        messages.success(self.request, "Thank you for your feedback!")
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        # Add session info to context
        if hasattr(self, 'private_session') and self.private_session:
            context['session'] = self.private_session
            context['session_type'] = 'private'
        elif hasattr(self, 'group_session') and self.group_session:
            context['session'] = self.group_session
            context['session_type'] = 'group'
        
        context['instructor'] = self.instructor
        context['title'] = 'Session Feedback'
        
        # Set active menu attributes
        context['active_menu'] = 'booking'
        context['active_submenu'] = 'student_dashboard'
        
        # Set the layout path
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context

class SessionFeedbackListView(LoginRequiredMixin, ListView):
    """View for instructors to see feedback for their sessions"""
    model = SessionFeedback
    context_object_name = 'feedbacks'
    template_name = 'session_feedback_list.html'
    paginate_by = 10
    
    def get_queryset(self):
        # Only instructors can see their feedback
        if not hasattr(self.request.user, 'instructor_profile'):
            return SessionFeedback.objects.none()
        
        instructor = self.request.user.instructor_profile
        
        # Get feedback for both private and group sessions
        return SessionFeedback.objects.filter(
            Q(private_session__instructor=instructor) |
            Q(group_session__instructor=instructor)
        ).select_related('user', 'private_session', 'group_session').order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        # Calculate average ratings
        ratings = self.get_queryset().values_list('rating', flat=True)
        if ratings:
            context['average_rating'] = sum(ratings) / len(ratings)
            
            # Rating distribution
            context['rating_counts'] = {
                i: ratings.filter(rating=i).count() for i in range(1, 6)
            }
            
            total = len(ratings)
            context['rating_percentages'] = {
                i: (context['rating_counts'][i] / total) * 100 if total > 0 else 0 
                for i in range(1, 6)
            }
        
        context['title'] = 'My Session Feedback'
        
        # Set active menu attributes
        context['active_menu'] = 'instructor'
        context['active_submenu'] = 'feedback'
        
        # Set the layout path
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context
    

class CreateSessionReportView(LoginRequiredMixin, CreateView):
    """View for instructors to create reports on sessions"""
    model = SessionReport
    template_name = 'session_report_form.html'
    fields = ['summary', 'topics_covered', 'student_progress', 'recommendations', 
              'materials_used', 'student_strengths', 'student_weaknesses']
    
    def get_success_url(self):
        return reverse('content:instructor_dashboard')
    
    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        
        # Verify the user is an instructor
        if not hasattr(request.user, 'instructor_profile'):
            raise Http404("Only instructors can create session reports")
        
        session_type = kwargs.get('session_type')
        session_id = kwargs.get('session_id')
        
        self.private_session = None
        self.group_session = None
        
        if session_type == 'private':
            self.private_session = get_object_or_404(
                PrivateSessionSlot, 
                id=session_id,
                instructor=request.user.instructor_profile
            )
        elif session_type == 'group':
            self.group_session = get_object_or_404(
                GroupSession,
                id=session_id,
                instructor=request.user.instructor_profile
            )
    
    def form_valid(self, form):
        # Set the session and instructor
        form.instance.instructor = self.request.user.instructor_profile
        
        if hasattr(self, 'private_session') and self.private_session:
            form.instance.session_type = 'private'
            form.instance.private_session = self.private_session
        elif hasattr(self, 'group_session') and self.group_session:
            form.instance.session_type = 'group'
            form.instance.group_session = self.group_session
        
        messages.success(self.request, "Session report created successfully!")
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        # Add session info to context
        if hasattr(self, 'private_session') and self.private_session:
            context['session'] = self.private_session
            context['session_type'] = 'private'
            context['student'] = self.private_session.student
        elif hasattr(self, 'group_session') and self.group_session:
            context['session'] = self.group_session
            context['session_type'] = 'group'
            context['students'] = self.group_session.students.all()
        
        context['title'] = 'Create Session Report'
        
        # Set active menu attributes
        context['active_menu'] = 'instructor'
        context['active_submenu'] = 'reports'
        
        # Set the layout path
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context

class SessionReportListView(LoginRequiredMixin, ListView):
    """View for instructors to see all their session reports"""
    model = SessionReport
    context_object_name = 'reports'
    template_name = 'session_report_list.html'
    paginate_by = 10
    
    def get_queryset(self):
        # Only instructors can see their reports
        if not hasattr(self.request.user, 'instructor_profile'):
            return SessionReport.objects.none()
        
        instructor = self.request.user.instructor_profile
        return SessionReport.objects.filter(instructor=instructor).order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        context['title'] = 'My Session Reports'
        
        # Set active menu attributes
        context['active_menu'] = 'instructor'
        context['active_submenu'] = 'reports'
        
        # Set the layout path
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context

class SessionReportDetailView(LoginRequiredMixin, DetailView):
    """View to display session report details"""
    model = SessionReport
    context_object_name = 'report'
    template_name = 'session_report_detail.html'
    pk_url_kwarg = 'report_id'
    
    def get_queryset(self):
        # Instructors can see their own reports, students can see reports for their sessions
        if hasattr(self.request.user, 'instructor_profile'):
            return SessionReport.objects.filter(instructor=self.request.user.instructor_profile)
        
        # Students can see reports for sessions they were in
        return SessionReport.objects.filter(
            Q(private_session__student=self.request.user) |
            Q(group_session__students=self.request.user)
        ).distinct()
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        report = self.get_object()
        context['title'] = f'Session Report: {report.get_session_display()}'
        
        # Determine if user is the instructor or a student
        context['is_instructor'] = hasattr(self.request.user, 'instructor_profile') and report.instructor == self.request.user.instructor_profile
        
        # Set active menu based on user role
        if context['is_instructor']:
            context['active_menu'] = 'instructor'
            context['active_submenu'] = 'reports'
        else:
            context['active_menu'] = 'booking'
            context['active_submenu'] = 'student_dashboard'
        
        # Set the layout path
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context
    

class ManageSessionAttendanceView(LoginRequiredMixin, TemplateView):
    """View for instructors to manage attendance for a group session"""
    template_name = 'manage_attendance.html'
    
    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        
        # Verify the user is an instructor
        if not hasattr(request.user, 'instructor_profile'):
            raise Http404("Only instructors can manage attendance")
        
        # Get the session
        session_id = kwargs.get('session_id')
        self.session = get_object_or_404(
            GroupSession, 
            id=session_id,
            instructor=request.user.instructor_profile
        )
    
    def post(self, request, *args, **kwargs):
        # Process attendance form submission
        for student_id, attendance_data in request.POST.items():
            if student_id.startswith('student_'):
                # Extract student ID from form field name
                student_id = student_id.split('_')[1]
                
                try:
                    student = User.objects.get(id=student_id)
                    
                    # Check if student is enrolled in this session
                    if not self.session.students.filter(id=student.id).exists():
                        continue
                    
                    # Get or create attendance record
                    attendance, created = SessionAttendance.objects.get_or_create(
                        session=self.session,
                        student=student
                    )
                    
                    # Update attendance status
                    attendance_status = request.POST.get(f'student_{student_id}')
                    if attendance_status == 'present':
                        attendance.attended = True
                        if not attendance.join_time:
                            attendance.join_time = timezone.now()
                    else:
                        attendance.attended = False
                    
                    # Get notes if provided
                    notes = request.POST.get(f'notes_{student_id}', '')
                    if notes.strip():
                        attendance.notes = notes
                    
                    attendance.save()
                    
                except User.DoesNotExist:
                    continue
        
        messages.success(request, "Attendance has been recorded successfully!")
        return redirect('content:group_session_detail', session_id=self.session.id)
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        context['session'] = self.session
        context['attendance_records'] = {}
        
        # Get enrolled students and their attendance records
        for student in self.session.students.all():
            attendance = SessionAttendance.objects.filter(
                session=self.session,
                student=student
            ).first()
            
            context['attendance_records'][student.id] = attendance
        
        context['title'] = f'Manage Attendance: {self.session.title}'
        
        # Set active menu attributes
        context['active_menu'] = 'instructor'
        context['active_submenu'] = 'instructor_dashboard'
        
        # Set the layout path
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context  


class LanguageListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """View to list and manage available languages"""
    model = Language
    context_object_name = 'languages'
    template_name = 'language_list.html'
    
    def test_func(self):
        # Only admin users can manage languages
        return self.request.user.is_superuser or self.request.user.is_staff
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        context['title'] = 'Language Management'
        
        # Set active menu attributes
        context['active_menu'] = 'admin'
        context['active_submenu'] = 'languages'
        
        # Set the layout path
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context

class LanguageCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """View to create a new language"""
    model = Language
    fields = ['name', 'code', 'is_active', 'flag_icon']
    template_name = 'language_form.html'
    success_url = reverse_lazy('content:language_list')
    
    def test_func(self):
        # Only admin users can create languages
        return self.request.user.is_superuser or self.request.user.is_staff
    
    def form_valid(self, form):
        messages.success(self.request, f"Language '{form.instance.name}' has been created successfully.")
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        context['title'] = 'Add New Language'
        context['submit_text'] = 'Create Language'
        
        # Set active menu attributes
        context['active_menu'] = 'admin'
        context['active_submenu'] = 'languages'
        
        # Set the layout path
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context

class LanguageUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """View to update an existing language"""
    model = Language
    fields = ['name', 'code', 'is_active', 'flag_icon']
    template_name = 'language_form.html'
    success_url = reverse_lazy('content:language_list')
    pk_url_kwarg = 'language_id'
    
    def test_func(self):
        # Only admin users can update languages
        return self.request.user.is_superuser or self.request.user.is_staff
    
    def form_valid(self, form):
        messages.success(self.request, f"Language '{form.instance.name}' has been updated successfully.")
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        context['title'] = 'Edit Language'
        context['submit_text'] = 'Update Language'
        
        # Set active menu attributes
        context['active_menu'] = 'admin'
        context['active_submenu'] = 'languages'
        
        # Set the layout path
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context

class LanguageLevelListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """View to list and manage available language proficiency levels"""
    model = LanguageLevel
    context_object_name = 'levels'
    template_name = 'language_level_list.html'
    
    def test_func(self):
        # Only admin users can manage language levels
        return self.request.user.is_superuser or self.request.user.is_staff
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        context['title'] = 'Language Level Management'
        
        # Set active menu attributes
        context['active_menu'] = 'admin'
        context['active_submenu'] = 'language_levels'
        
        # Set the layout path
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context

class LanguageLevelCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """View to create a new language proficiency level"""
    model = LanguageLevel
    fields = ['code', 'name', 'description']
    template_name = 'language_level_form.html'
    success_url = reverse_lazy('content:language_level_list')
    
    def test_func(self):
        # Only admin users can create language levels
        return self.request.user.is_superuser or self.request.user.is_staff
    
    def form_valid(self, form):
        messages.success(self.request, f"Language level '{form.instance.name}' has been created successfully.")
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        context['title'] = 'Add New Language Level'
        context['submit_text'] = 'Create Level'
        
        # Set active menu attributes
        context['active_menu'] = 'admin'
        context['active_submenu'] = 'language_levels'
        
        # Set the layout path
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context

class LanguageLevelUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """View to update an existing language proficiency level"""
    model = LanguageLevel
    fields = ['code', 'name', 'description']
    template_name = 'language_level_form.html'
    success_url = reverse_lazy('content:language_level_list')
    pk_url_kwarg = 'level_id'
    
    def test_func(self):
        # Only admin users can update language levels
        return self.request.user.is_superuser or self.request.user.is_staff
    
    def form_valid(self, form):
        messages.success(self.request, f"Language level '{form.instance.name}' has been updated successfully.")
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        context['title'] = 'Edit Language Level'
        context['submit_text'] = 'Update Level'
        
        # Set active menu attributes
        context['active_menu'] = 'admin'
        context['active_submenu'] = 'language_levels'
        
        # Set the layout path
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context        
