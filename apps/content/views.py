from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View, TemplateView, RedirectView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.http import JsonResponse
from django.contrib import messages
from django.db.models import Q, Count, Avg
from django.utils import timezone
from django.contrib.auth.models import User
from web_project import TemplateLayout
from web_project.template_helpers.theme import TemplateHelper

# Import models - adjust these based on your actual model structure
from .models import (
    Language, LanguageLevel, Course as Session,  # Rename the import for clarity
     Lesson
)
from .forms import (
    CourseForm as SessionForm,  
    CourseFilterForm as SessionFilterForm  
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
        
        # Add information about teacher status
        is_teacher = hasattr(user, 'is_teacher') and user.is_teacher
        context['is_teacher'] = is_teacher
        
        # Add helpful messaging for non-teachers
        if not is_teacher:
            context['non_teacher_message'] = "This dashboard is designed for instructors. You can create an instructor profile to start teaching on the platform."
        
        if has_instructor_profile:
            instructor = user.instructor_profile
            context['instructor'] = instructor
            
            # Get private session slots
            now = timezone.now()
            context['upcoming_private_slots'] = PrivateSessionSlot.objects.filter(
                instructor=instructor,
                start_time__gt=now
            ).order_by('start_time')
            
            # Group slots by status
            context['available_slots'] = context['upcoming_private_slots'].filter(status='available')
            context['booked_slots'] = context['upcoming_private_slots'].filter(status='booked')
            
            # Get past slots
            context['past_slots'] = PrivateSessionSlot.objects.filter(
                instructor=instructor,
                start_time__lt=now
            ).order_by('-start_time')[:10]
            
            # Get group sessions
            context['upcoming_group_sessions'] = GroupSession.objects.filter(
                instructor=instructor,
                start_time__gt=now
            ).order_by('start_time')
            
            # Get past group sessions
            context['past_group_sessions'] = GroupSession.objects.filter(
                instructor=instructor,
                start_time__lt=now
            ).order_by('-start_time')[:10]
            
            # Get reviews
            context['recent_reviews'] = InstructorReview.objects.filter(
                instructor=instructor
            ).order_by('-created_at')[:5]
            
            # Calculate statistics
            context['total_private_sessions'] = PrivateSessionSlot.objects.filter(
                instructor=instructor,
                status__in=['completed', 'booked']
            ).count()
            
            context['total_group_sessions'] = GroupSession.objects.filter(
                instructor=instructor
            ).count()
            
            context['total_students'] = len(set(list(PrivateSessionSlot.objects.filter(
                instructor=instructor,
                status__in=['completed', 'booked']
            ).values_list('student', flat=True)) + list(GroupSession.objects.filter(
                instructor=instructor
            ).values_list('students', flat=True))))
            
            context['rating'] = instructor.rating
        else:
            # Provide an option to create an instructor profile
            context['create_profile_url'] = reverse('content:create_instructor_profile')
        
        # Set active menu attributes
        context['active_menu'] = 'content'
        context['active_submenu'] = 'instructor_dashboard'
        
        # Set the layout path using TemplateHelper
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context

class SessionForm(LoginRequiredMixin, UpdateView):
    """Base form for both private and group session slot creation/editing"""
    template_name = 'session_form.html'


class CreatePrivateSessionSlotView(SessionForm):
    """View for instructors to create private session slots"""
    model = PrivateSessionSlot
    fields = ['start_time', 'duration_minutes', 'language', 'level']
    success_url = reverse_lazy('content:instructor_dashboard')
    
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
        context['active_menu'] = 'content'
        context['active_submenu'] = 'instructor_dashboard'
        
        # Set the layout path using TemplateHelper
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context

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


class CreatePrivateSessionSlotView(SessionForm):
    """View for instructors to create private session slots"""
    model = PrivateSessionSlot
    fields = ['start_time', 'duration_minutes', 'language', 'level']
    success_url = reverse_lazy('content:instructor_dashboard')
    
    def form_valid(self, form):
        # Set the instructor
        form.instance.instructor = self.request.user.instructor_profile
        
        # Set status to available
        form.instance.status = 'available'
        
        # Calculate end_time based on duration
        form.instance.end_time = form.instance.start_time + timezone.timedelta(minutes=form.instance.duration_minutes)
        
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
        context['active_menu'] = 'content'
        context['active_submenu'] = 'instructor_dashboard'
        
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


class CreateGroupSessionView(SessionForm):
    """View for instructors to create group sessions"""
    model = GroupSession
    fields = ['title', 'description', 'language', 'level', 'start_time', 
              'duration_minutes', 'max_students', 'price']
    success_url = reverse_lazy('content:instructor_dashboard')
    
    def form_valid(self, form):
        # Set the instructor
        form.instance.instructor = self.request.user.instructor_profile
        
        # Set status to scheduled
        form.instance.status = 'scheduled'
        
        # Calculate end_time based on duration
        form.instance.end_time = form.instance.start_time + timezone.timedelta(minutes=form.instance.duration_minutes)
        
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
        context['active_menu'] = 'content'
        context['active_submenu'] = 'instructor_dashboard'
        
        # Set the layout path using TemplateHelper
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context


class UpdateGroupSessionView(SessionForm):
    """View for instructors to update group sessions"""
    model = GroupSession
    fields = ['title', 'description', 'language', 'level', 'start_time', 
              'duration_minutes', 'max_students', 'price']
    pk_url_kwarg = 'session_id'
    success_url = reverse_lazy('content:instructor_dashboard')
    
    def test_func(self):
        result = super().test_func()
        if not result:
            return False
        
        # Check if the instructor owns this session
        session = self.get_object()
        return session.instructor.user == self.request.user
    
    def form_valid(self, form):
        # Don't allow reducing max_students below current enrollment
        if form.instance.max_students < self.object.students.count():
            form.instance.max_students = self.object.students.count()
            messages.warning(self.request, "Maximum students cannot be less than current enrollment.")
        
        # Recalculate end_time based on duration
        form.instance.end_time = form.instance.start_time + timezone.timedelta(minutes=form.instance.duration_minutes)
        
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        # Get languages and levels for selection
        context['languages'] = Language.objects.filter(is_active=True)
        context['levels'] = LanguageLevel.objects.all()
        
        context['title'] = 'Edit Group Session'
        context['is_private'] = False
        
        # Set active menu attributes
        context['active_menu'] = 'content'
        context['active_submenu'] = 'instructor_dashboard'
        
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