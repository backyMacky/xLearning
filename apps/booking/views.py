from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView, View, FormView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.http import JsonResponse
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, Count, Q
from web_project import TemplateLayout
from web_project.template_helpers.theme import TemplateHelper

# Import models
from .models import (
    Instructor, PrivateSessionSlot, GroupSession, 
    InstructorReview, CreditTransaction
)

# For the credit purchase form
from django import forms


class BookPrivateSessionView(LoginRequiredMixin, UserPassesTestMixin, View):
    """View to book a private session with an instructor"""
    
    def test_func(self):
        return hasattr(self.request.user, 'is_student') and self.request.user.is_student
    
    def get(self, request, slot_id):
        slot = get_object_or_404(PrivateSessionSlot, id=slot_id, status='available')
        
        # Check if slot is still available
        if slot.status != 'available':
            messages.error(request, "This session is no longer available.")
            return redirect('content:instructor_detail', username=slot.instructor.user.username)
        
        # Get student's credit balance
        credit_balance = 0
        if CreditTransaction.objects.filter(student=request.user).exists():
            last_transaction = CreditTransaction.objects.filter(student=request.user).latest('created_at')
            credit_balance = last_transaction.get_balance()
        
        return render(request, 'book_private_session.html', {
            'slot': slot,
            'instructor': slot.instructor,
            'credit_balance': credit_balance,
            'session_cost': slot.duration_minutes / 60,  # Assume 1 credit per hour
            'active_menu': 'booking',
            'active_submenu': 'instructor_list',
            'layout_path': TemplateHelper.set_layout("layout_vertical.html")
        })
    
    def post(self, request, slot_id):
        slot = get_object_or_404(PrivateSessionSlot, id=slot_id, status='available')
        
        # Check if slot is still available
        if slot.status != 'available':
            messages.error(request, "This session is no longer available.")
            return redirect('content:instructor_detail', username=slot.instructor.user.username)
        
        # Check if student has enough credits
        credit_balance = 0
        if CreditTransaction.objects.filter(student=request.user).exists():
            last_transaction = CreditTransaction.objects.filter(student=request.user).latest('created_at')
            credit_balance = last_transaction.get_balance()
        
        # Calculate session cost (assume 1 credit per hour)
        session_cost = slot.duration_minutes / 60
        
        if credit_balance < session_cost:
            messages.error(request, "You don't have enough credits to book this session.")
            return redirect('booking:purchase_credits')
        
        # Book the slot
        success, message = slot.book(request.user)
        
        if success:
            # Deduct credits
            CreditTransaction.objects.create(
                student=request.user,
                amount=session_cost,
                description=f"Private session with {slot.instructor.user.username} on {slot.start_time}",
                transaction_type='deduction',
                private_session=slot
            )
            
            messages.success(request, "Session booked successfully!")
            return redirect('booking:my_sessions')
        else:
            messages.error(request, message)
            return redirect('content:instructor_detail', username=slot.instructor.user.username)


class CancelPrivateSessionView(LoginRequiredMixin, View):
    """View to cancel a booked private session"""
    
    def get(self, request, slot_id):
        # Find the session (could be booked by student or created by instructor)
        if hasattr(request.user, 'is_student') and request.user.is_student:
            slot = get_object_or_404(PrivateSessionSlot, id=slot_id, student=request.user, status='booked')
        else:
            # For instructors
            instructor = get_object_or_404(Instructor, user=request.user)
            slot = get_object_or_404(PrivateSessionSlot, id=slot_id, instructor=instructor)
        
        return render(request, 'cancel_private_session.html', {
            'slot': slot,
            'active_menu': 'booking',
            'active_submenu': 'my_sessions',
            'layout_path': TemplateHelper.set_layout("layout_vertical.html")
        })
    
    def post(self, request, slot_id):
        # Find the session (could be booked by student or created by instructor)
        if hasattr(request.user, 'is_student') and request.user.is_student:
            slot = get_object_or_404(PrivateSessionSlot, id=slot_id, student=request.user, status='booked')
        else:
            # For instructors
            instructor = get_object_or_404(Instructor, user=request.user)
            slot = get_object_or_404(PrivateSessionSlot, id=slot_id, instructor=instructor)
        
        # Cancel the session
        success, message = slot.cancel(request.user)
        
        if success:
            messages.success(request, message)
            
            # If this was cancelled by the instructor and had a student booked,
            # issue a refund to the student
            if hasattr(request.user, 'is_teacher') and request.user.is_teacher and slot.student:
                # Calculate refund amount (1 credit per hour)
                refund_amount = slot.duration_minutes / 60
                
                CreditTransaction.objects.create(
                    student=slot.student,
                    amount=refund_amount,
                    description=f"Refund for cancelled session with {request.user.username}",
                    transaction_type='refund',
                    private_session=slot
                )
        else:
            messages.error(request, message)
        
        # Redirect to appropriate dashboard
        if hasattr(request.user, 'is_student') and request.user.is_student:
            return redirect('booking:my_sessions')
        else:
            return redirect('content:instructor_dashboard')


class EnrollGroupSessionView(LoginRequiredMixin, UserPassesTestMixin, View):
    """View to enroll in a group session"""
    
    def test_func(self):
        return hasattr(self.request.user, 'is_student') and self.request.user.is_student
    
    def get(self, request, session_id):
        session = get_object_or_404(GroupSession, id=session_id, status='scheduled')
        
        # Check if already enrolled
        if session.students.filter(id=request.user.id).exists():
            messages.info(request, "You are already enrolled in this session.")
            return redirect('content:group_session_detail', session_id=session.id)
        
        # Check if session is full
        if session.is_full:
            messages.error(request, "This session is full.")
            return redirect('content:group_session_detail', session_id=session.id)
        
        # Get student's credit balance
        credit_balance = 0
        if CreditTransaction.objects.filter(student=request.user).exists():
            last_transaction = CreditTransaction.objects.filter(student=request.user).latest('created_at')
            credit_balance = last_transaction.get_balance()
        
        return render(request, 'enroll_group_session.html', {
            'session': session,
            'instructor': session.instructor,
            'credit_balance': credit_balance,
            'active_menu': 'booking',
            'active_submenu': 'group_sessions',
            'layout_path': TemplateHelper.set_layout("layout_vertical.html")
        })
    
    def post(self, request, session_id):
        session = get_object_or_404(GroupSession, id=session_id, status='scheduled')
        
        # Check if session is full
        if session.is_full:
            messages.error(request, "This session is full.")
            return redirect('content:group_session_detail', session_id=session.id)
        
        # Check if student has enough credits
        credit_balance = 0
        if CreditTransaction.objects.filter(student=request.user).exists():
            last_transaction = CreditTransaction.objects.filter(student=request.user).latest('created_at')
            credit_balance = last_transaction.get_balance()
        
        if credit_balance < session.price:
            messages.error(request, "You don't have enough credits to enroll in this session.")
            return redirect('booking:purchase_credits')
        
        # Enroll in the session
        success, message = session.enroll_student(request.user)
        
        if success:
            # Deduct credits
            CreditTransaction.objects.create(
                student=request.user,
                amount=session.price,
                description=f"Enrollment in group session '{session.title}' on {session.start_time}",
                transaction_type='deduction',
                group_session=session
            )
            
            messages.success(request, "Successfully enrolled in the group session!")
            return redirect('content:group_session_detail', session_id=session.id)
        else:
            messages.error(request, message)
            return redirect('content:group_session_detail', session_id=session.id)


class UnenrollGroupSessionView(LoginRequiredMixin, UserPassesTestMixin, View):
    """View to unenroll from a group session"""
    
    def test_func(self):
        return hasattr(self.request.user, 'is_student') and self.request.user.is_student
    
    def get(self, request, session_id):
        session = get_object_or_404(GroupSession, id=session_id)
        
        # Check if enrolled
        if not session.students.filter(id=request.user.id).exists():
            messages.error(request, "You are not enrolled in this session.")
            return redirect('content:group_session_detail', session_id=session.id)
        
        return render(request, 'unenroll_group_session.html', {
            'session': session,
            'active_menu': 'booking',
            'active_submenu': 'my_sessions',
            'layout_path': TemplateHelper.set_layout("layout_vertical.html")
        })
    
    def post(self, request, session_id):
        session = get_object_or_404(GroupSession, id=session_id)
        
        # Check if enrolled
        if not session.students.filter(id=request.user.id).exists():
            messages.error(request, "You are not enrolled in this session.")
            return redirect('content:group_session_detail', session_id=session.id)
        
        # Attempt to unenroll
        success, message = session.unenroll_student(request.user)
        
        if success:
            # Refund credits
            CreditTransaction.objects.create(
                student=request.user,
                amount=session.price,
                description=f"Refund for unenrollment from group session '{session.title}'",
                transaction_type='refund',
                group_session=session
            )
            
            messages.success(request, message)
        else:
            messages.error(request, message)
        
        return redirect('booking:my_sessions')


class PurchaseCreditsForm(forms.Form):
    """Form for purchasing credits"""
    CREDIT_CHOICES = [
        (5, '5 Credits - $25'),
        (10, '10 Credits - $45'),
        (20, '20 Credits - $80'),
        (50, '50 Credits - $180'),
    ]
    
    credit_package = forms.ChoiceField(
        choices=CREDIT_CHOICES,
        widget=forms.RadioSelect(),
        label="Select Credit Package"
    )
    
    payment_method = forms.ChoiceField(
        choices=[
            ('credit_card', 'Credit Card'),
            ('paypal', 'PayPal'),
        ],
        widget=forms.RadioSelect(),
        label="Payment Method"
    )
    
    # In a real application, you would add fields for payment information
    # such as credit card details or redirect to a payment gateway


class PurchaseCreditsView(LoginRequiredMixin, UserPassesTestMixin, FormView):
    """View for students to purchase credits"""
    template_name = 'purchase_credits.html'
    form_class = PurchaseCreditsForm
    success_url = reverse_lazy('booking:transaction_history')
    
    def test_func(self):
        return hasattr(self.request.user, 'is_student') and self.request.user.is_student
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        # Get student's current credit balance
        credit_balance = 0
        if CreditTransaction.objects.filter(student=self.request.user).exists():
            last_transaction = CreditTransaction.objects.filter(student=self.request.user).latest('created_at')
            credit_balance = last_transaction.get_balance()
        
        context['credit_balance'] = credit_balance
        
        # Set active menu attributes
        context['active_menu'] = 'booking'
        context['active_submenu'] = 'credits'
        
        # Set the layout path using TemplateHelper
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context
    
    def form_valid(self, form):
        # Get the selected credit package
        credit_package = int(form.cleaned_data['credit_package'])
        
        # In a real application, you would integrate with a payment gateway here
        # For this demo, we'll assume the payment was successful
        
        # Create credit transaction
        CreditTransaction.objects.create(
            student=self.request.user,
            amount=credit_package,
            description=f"Purchase of {credit_package} credits",
            transaction_type='purchase'
        )
        
        messages.success(self.request, f"Successfully purchased {credit_package} credits!")
        return super().form_valid(form)


class TransactionHistoryView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """View for students to view their credit transaction history"""
    model = CreditTransaction
    context_object_name = 'transactions'
    template_name = 'transaction_history.html'
    paginate_by = 20
    
    def test_func(self):
        return hasattr(self.request.user, 'is_student') and self.request.user.is_student
    
    def get_queryset(self):
        return CreditTransaction.objects.filter(
            student=self.request.user
        ).order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        # Calculate current balance
        credit_balance = 0
        if CreditTransaction.objects.filter(student=self.request.user).exists():
            last_transaction = CreditTransaction.objects.filter(student=self.request.user).latest('created_at')
            credit_balance = last_transaction.get_balance()
        
        context['credit_balance'] = credit_balance
        
        # Set active menu attributes
        context['active_menu'] = 'booking'
        context['active_submenu'] = 'credits'
        
        # Set the layout path using TemplateHelper
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context


class BookingDashboardView(LoginRequiredMixin, TemplateView):
    """Dashboard for booking system showing upcoming sessions and available credits"""
    template_name = 'booking_dashboard.html'
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        user = self.request.user
        now = timezone.now()
        
        # Different views depending on user type
        if hasattr(user, 'is_teacher') and user.is_teacher:
            # Teacher/instructor view
            if hasattr(user, 'instructor_profile'):
                instructor = user.instructor_profile
                
                # Get upcoming private sessions
                context['upcoming_private_sessions'] = PrivateSessionSlot.objects.filter(
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
                
                # Calculate session statistics
                context['total_hours_booked'] = sum([
                    session.duration_minutes / 60 for session in context['upcoming_private_sessions']
                ]) + sum([
                    session.duration_minutes / 60 * session.students.count() 
                    for session in context['upcoming_group_sessions']
                ])
                
                # Count total students
                student_ids = set()
                for session in context['upcoming_private_sessions']:
                    if session.student:
                        student_ids.add(session.student.id)
                
                for session in context['upcoming_group_sessions']:
                    student_ids.update(session.students.values_list('id', flat=True))
                
                context['total_students'] = len(student_ids)
                
                # Count available slots
                context['available_slots'] = PrivateSessionSlot.objects.filter(
                    instructor=instructor,
                    status='available',
                    start_time__gt=now
                ).count()
            
            # Set active menu attributes
            context['active_menu'] = 'booking'
            context['active_submenu'] = 'instructor_booking'
        
        else:
            # Student view
            # Get upcoming private sessions
            context['upcoming_private_sessions'] = PrivateSessionSlot.objects.filter(
                student=user,
                status='booked',
                start_time__gt=now
            ).order_by('start_time')
            
            # Get upcoming group sessions
            context['upcoming_group_sessions'] = GroupSession.objects.filter(
                students=user,
                status='scheduled',
                start_time__gt=now
            ).order_by('start_time')
            
            # Get student's credit balance
            credit_balance = 0
            if CreditTransaction.objects.filter(student=user).exists():
                last_transaction = CreditTransaction.objects.filter(student=user).latest('created_at')
                credit_balance = last_transaction.get_balance()
            
            context['credit_balance'] = credit_balance
            
            # Get available instructors for booking
            context['available_instructors'] = Instructor.objects.filter(
                is_available=True
            ).select_related('user')[:4]
            
            # Set active menu attributes
            context['active_menu'] = 'booking'
            context['active_submenu'] = 'student_booking'
        
        # Set the layout path using TemplateHelper
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context


class MySessionsView(LoginRequiredMixin, TemplateView):
    """View for students to see all their booked sessions"""
    template_name = 'my_sessions.html'
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        user = self.request.user
        now = timezone.now()
        
        # Determine if user is student or instructor
        is_student = hasattr(user, 'is_student') and user.is_student
        is_instructor = hasattr(user, 'is_teacher') and user.is_teacher and hasattr(user, 'instructor_profile')
        
        if is_student:
            # Private sessions
            context['upcoming_private_sessions'] = PrivateSessionSlot.objects.filter(
                student=user,
                status='booked',
                start_time__gt=now
            ).order_by('start_time')
            
            context['past_private_sessions'] = PrivateSessionSlot.objects.filter(
                student=user,
                start_time__lt=now
            ).order_by('-start_time')[:10]
            
            # Group sessions
            context['upcoming_group_sessions'] = GroupSession.objects.filter(
                students=user,
                status='scheduled',
                start_time__gt=now
            ).order_by('start_time')
            
            context['past_group_sessions'] = GroupSession.objects.filter(
                students=user,
                start_time__lt=now
            ).order_by('-start_time')[:10]
            
            # Credit balance
            credit_balance = 0
            if CreditTransaction.objects.filter(student=user).exists():
                last_transaction = CreditTransaction.objects.filter(student=user).latest('created_at')
                credit_balance = last_transaction.get_balance()
            
            context['credit_balance'] = credit_balance
            
            # Show the student view
            context['is_student_view'] = True
            
        elif is_instructor:
            instructor = user.instructor_profile
            
            # Private sessions
            context['upcoming_private_sessions'] = PrivateSessionSlot.objects.filter(
                instructor=instructor,
                status='booked',
                start_time__gt=now
            ).order_by('start_time')
            
            context['past_private_sessions'] = PrivateSessionSlot.objects.filter(
                instructor=instructor,
                start_time__lt=now
            ).order_by('-start_time')[:10]
            
            # Group sessions
            context['upcoming_group_sessions'] = GroupSession.objects.filter(
                instructor=instructor,
                status='scheduled',
                start_time__gt=now
            ).order_by('start_time')
            
            context['past_group_sessions'] = GroupSession.objects.filter(
                instructor=instructor,
                start_time__lt=now
            ).order_by('-start_time')[:10]
            
            # Available slots
            context['available_slots'] = PrivateSessionSlot.objects.filter(
                instructor=instructor,
                status='available',
                start_time__gt=now
            ).order_by('start_time')
            
            # Show the instructor view
            context['is_student_view'] = False
        
        # Set active menu attributes
        context['active_menu'] = 'booking'
        context['active_submenu'] = 'my_sessions'
        
        # Set the layout path using TemplateHelper
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context 