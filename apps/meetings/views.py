from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.http import JsonResponse
from django.contrib.auth.models import User
from django.utils import timezone
from django.contrib import messages
from datetime import datetime, timedelta
from web_project import TemplateLayout

from .models import Meeting, TeacherAvailability
from apps.content.models import Course

class MeetingListView(LoginRequiredMixin, ListView):
    """View for listing all meetings"""
    model = Meeting
    template_name = 'meeting_list.html'
    context_object_name = 'meetings'
    
    def get_queryset(self):
        now = timezone.now()
        
        if hasattr(self.request.user, 'is_teacher') and self.request.user.is_teacher:
            # Get teacher's meetings
            return Meeting.objects.filter(teacher=self.request.user).order_by('start_time')
        else:
            # Get student's meetings
            return Meeting.objects.filter(students=self.request.user).order_by('start_time')
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        # Set active menu attributes
        context['active_menu'] = 'meetings'
        context['active_submenu'] = 'meeting-list'
        
        now = timezone.now()
        
        # Split meetings into upcoming and past
        meetings = self.get_queryset()
        context['upcoming_meetings'] = meetings.filter(start_time__gte=now)
        context['past_meetings'] = meetings.filter(start_time__lt=now)
        
        return context

class MeetingDetailView(LoginRequiredMixin, DetailView):
    """View for meeting details"""
    model = Meeting
    template_name = 'meeting_detail.html'
    context_object_name = 'meeting'
    pk_url_kwarg = 'meeting_id'
    
    def get(self, request, *args, **kwargs):
        meeting = self.get_object()
        
        # Check if user has access to this meeting
        if hasattr(request.user, 'is_teacher') and request.user.is_teacher and meeting.teacher != request.user:
            messages.error(request, "You don't have access to this meeting.")
            return redirect('meetings:meeting_list')
        
        if not hasattr(request.user, 'is_teacher') or not request.user.is_teacher:
            if request.user not in meeting.students.all():
                messages.error(request, "You are not enrolled in this meeting.")
                return redirect('meetings:meeting_list')
        
        return super().get(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        # Set active menu attributes
        context['active_menu'] = 'meetings'
        context['active_submenu'] = 'meeting-list'
        
        # Add additional context
        meeting = self.get_object()
        context['is_teacher'] = hasattr(self.request.user, 'is_teacher') and self.request.user.is_teacher
        context['is_student'] = not context['is_teacher']
        context['now'] = timezone.now()
        
        # Check if meeting is active
        context['is_active'] = (
            meeting.start_time <= timezone.now() and 
            meeting.start_time + timedelta(minutes=meeting.duration) >= timezone.now()
        )
        
        return context

class CreateMeetingView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """View for creating new meetings"""
    model = Meeting
    template_name = 'create_meeting.html'
    fields = ['title', 'start_time', 'duration', 'meeting_link']
    
    def test_func(self):
        # Only teachers can create meetings  & superuser can create
        return hasattr(self.request.user, 'is_teacher') and self.request.user.is_teacher or self.request.user.is_superuser or self.request.user.is_staff
    
    def get_success_url(self):
        return reverse('meetings:meeting_detail', kwargs={'meeting_id': self.object.id})
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        # Set active menu attributes
        context['active_menu'] = 'meetings'
        context['active_submenu'] = 'create-meeting'
        
        # Get students the teacher has access to (from their courses)
        if hasattr(self.request.user, 'is_teacher') and self.request.user.is_teacher:
            courses = Course.objects.filter(teacher=self.request.user)
            student_ids = set()
            for course in courses:
                student_ids.update(course.students.values_list('id', flat=True))
            
            context['students'] = User.objects.filter(id__in=student_ids)
            context['courses'] = courses
        
        return context
    
    def form_valid(self, form):
        # Set the teacher to the current user
        form.instance.teacher = self.request.user
        
        # Save the form to create the meeting
        response = super().form_valid(form)
        
        # Add selected students to the meeting
        student_ids = self.request.POST.getlist('students')
        for student_id in student_ids:
            try:
                student = User.objects.get(id=student_id)
                self.object.students.add(student)
            except User.DoesNotExist:
                pass
        
        # If no meeting link was provided, generate one
        if not form.instance.meeting_link:
            form.instance.meeting_link = f"https://meet.google.com/{self.request.user.username}-{timezone.now().strftime('%Y%m%d%H%M')}"
            form.instance.save()
        
        messages.success(self.request, "Meeting created successfully!")
        return response

class EditMeetingView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """View for editing meetings"""
    model = Meeting
    template_name = 'edit_meeting.html'
    fields = ['title', 'start_time', 'duration', 'meeting_link']
    pk_url_kwarg = 'meeting_id'
    
    def test_func(self):
        # Only the teacher who created the meeting can edit it
        meeting = self.get_object()
        return (hasattr(self.request.user, 'is_teacher') and 
                self.request.user.is_teacher and 
                meeting.teacher == self.request.user)
    
    def get_success_url(self):
        return reverse('meetings:meeting_detail', kwargs={'meeting_id': self.object.id})
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        # Set active menu attributes
        context['active_menu'] = 'meetings'
        context['active_submenu'] = 'meeting-list'
        
        # Get students the teacher has access to (from their courses)
        courses = Course.objects.filter(teacher=self.request.user)
        student_ids = set()
        for course in courses:
            student_ids.update(course.students.values_list('id', flat=True))
        
        context['students'] = User.objects.filter(id__in=student_ids)
        context['courses'] = courses
        
        # Get currently selected students
        context['selected_students'] = self.object.students.all().values_list('id', flat=True)
        
        return context
    
    def form_valid(self, form):
        response = super().form_valid(form)
        
        # Update students
        if 'students' in self.request.POST:
            self.object.students.clear()  # Remove existing students
            
            student_ids = self.request.POST.getlist('students')
            for student_id in student_ids:
                try:
                    student = User.objects.get(id=student_id)
                    self.object.students.add(student)
                except User.DoesNotExist:
                    pass
        
        messages.success(self.request, "Meeting updated successfully!")
        return response

class CancelMeetingView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """View for canceling/deleting meetings"""
    model = Meeting
    template_name = 'confirm_cancel.html'
    context_object_name = 'meeting'
    pk_url_kwarg = 'meeting_id'
    
    def test_func(self):
        # Only the teacher who created the meeting can cancel it
        meeting = self.get_object()
        return (hasattr(self.request.user, 'is_teacher') and 
                self.request.user.is_teacher and 
                meeting.teacher == self.request.user)
    
    def get_success_url(self):
        return reverse('meetings:meeting_list')
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        # Set active menu attributes
        context['active_menu'] = 'meetings'
        context['active_submenu'] = 'meeting-list'
        
        return context
    
    def delete(self, request, *args, **kwargs):
        meeting = self.get_object()
        
        # Check if meeting is in the past
        if meeting.start_time < timezone.now():
            messages.error(request, "Cannot delete a meeting that has already occurred.")
            return redirect('meetings:meeting_detail', meeting_id=meeting.id)
        
        # Delete the meeting
        response = super().delete(request, *args, **kwargs)
        
        messages.success(request, "Meeting cancelled successfully.")
        return response

class SendReminderView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """View for sending reminders for a meeting"""
    model = Meeting
    template_name = 'meeting_detail.html'  # Redirect to detail page after sending
    pk_url_kwarg = 'meeting_id'
    
    def test_func(self):
        # Only the teacher who created the meeting can send reminders
        meeting = self.get_object()
        return (hasattr(self.request.user, 'is_teacher') and 
                self.request.user.is_teacher and 
                meeting.teacher == self.request.user)
    
    def get(self, request, *args, **kwargs):
        meeting = self.get_object()
        
        # Send reminder
        meeting.send_reminders()
        
        messages.success(request, "Reminders sent successfully!")
        return redirect('meetings:meeting_detail', meeting_id=meeting.id)

class AvailabilityListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """View for listing teacher availability slots"""
    model = TeacherAvailability
    template_name = 'availability_list.html'
    context_object_name = 'availability_slots'
    
    """
    def test_func(self):
        # Only teachers can manage their availability
        return hasattr(self.request.user, 'is_teacher') and self.request.user.is_teacher
    """
    def test_func(self):
        # Allow all users to access
        return True

    def get_queryset(self):
        return TeacherAvailability.objects.filter(teacher=self.request.user).order_by('day_of_week', 'start_time')
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        # Set active menu attributes
        context['active_menu'] = 'meetings'
        context['active_submenu'] = 'availability'
        
        # Add day names for reference
        context['days'] = [
            'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'
        ]
        
        return context

class CreateAvailabilityView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """View for creating availability slots"""
    model = TeacherAvailability
    template_name = 'create_availability.html'
    fields = ['day_of_week', 'start_time', 'end_time']
    
    """
    def test_func(self):
        # Only teachers can create availability slots
        return hasattr(self.request.user, 'is_teacher') and self.request.user.is_teacher
    """
    
    def test_func(self):
        # Allow all users to access
        return True

    def get_success_url(self):
        return reverse('meetings:availability_list')
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        # Set active menu attributes
        context['active_menu'] = 'meetings'
        context['active_submenu'] = 'availability'
        
        # Add day choices
        context['day_choices'] = [
            (0, 'Monday'),
            (1, 'Tuesday'),
            (2, 'Wednesday'),
            (3, 'Thursday'),
            (4, 'Friday'),
            (5, 'Saturday'),
            (6, 'Sunday'),
        ]
        
        return context
    
    def form_valid(self, form):
        # Set the teacher to the current user
        form.instance.teacher = self.request.user
        
        messages.success(self.request, "Availability slot created successfully!")
        return super().form_valid(form)

class DeleteAvailabilityView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """View for deleting availability slots"""
    model = TeacherAvailability
    template_name = 'confirm_delete_availability.html'
    context_object_name = 'availability'
    pk_url_kwarg = 'availability_id'
    
    def test_func(self):
        # Only the teacher who created the availability can delete it
        availability = self.get_object()
        return (hasattr(self.request.user, 'is_teacher') and 
                self.request.user.is_teacher and 
                availability.teacher == self.request.user)
    
    def get_success_url(self):
        return reverse('meetings:availability_list')
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        # Set active menu attributes
        context['active_menu'] = 'meetings'
        context['active_submenu'] = 'availability'
        
        return context

class CalendarView(LoginRequiredMixin, TemplateView):
    """View for calendar with meetings and availability"""
    template_name = 'calendar.html'
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        # Set active menu attributes
        context['active_menu'] = 'meetings'
        context['active_submenu'] = 'calendar'
        
        now = timezone.now()
        user = self.request.user
        
        # Get meetings data for the calendar
        if hasattr(user, 'is_teacher') and user.is_teacher:
            # Teacher's meetings
            meetings = Meeting.objects.filter(teacher=user)
            
            # Teacher's availability (for calendar display)
            availability_slots = TeacherAvailability.objects.filter(teacher=user)
            context['availability_slots'] = availability_slots
        else:
            # Student's meetings
            meetings = Meeting.objects.filter(students=user)
        
        context['meetings'] = meetings
        
        # Format calendar data
        calendar_events = []
        for meeting in meetings:
            end_time = meeting.start_time + timedelta(minutes=meeting.duration)
            
            calendar_events.append({
                'id': meeting.id,
                'title': meeting.title,
                'start': meeting.start_time.isoformat(),
                'end': end_time.isoformat(),
                'url': reverse('meetings:meeting_detail', kwargs={'meeting_id': meeting.id}),
                'classNames': ['bg-primary', 'text-white'],
            })
        
        # Add availability slots to calendar (for teachers)
        if hasattr(user, 'is_teacher') and user.is_teacher and 'availability_slots' in context:
            for slot in context['availability_slots']:
                # Calculate dates for the current week
                today = timezone.now().date()
                week_start = today - timedelta(days=today.weekday())
                slot_date = week_start + timedelta(days=slot.day_of_week)
                
                # Create datetime objects
                slot_start = timezone.make_aware(datetime.combine(slot_date, slot.start_time))
                slot_end = timezone.make_aware(datetime.combine(slot_date, slot.end_time))
                
                calendar_events.append({
                    'id': f'avail_{slot.id}',
                    'title': 'Available',
                    'start': slot_start.isoformat(),
                    'end': slot_end.isoformat(),
                    'classNames': ['bg-success', 'text-white'],
                    'recurring': True,
                })
        
        context['calendar_events'] = calendar_events
        
        return context