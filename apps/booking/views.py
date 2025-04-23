from django.conf import settings
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView, View, FormView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.http import JsonResponse
from django.contrib import messages
from django.utils import timezone
from django.db import models
from django.db.models import Sum, Count, Q
from apps.content.models import PrivateSession
from web_project import TemplateLayout
from web_project.template_helpers.theme import TemplateHelper

from .models import (
    Instructor, PrivateSessionSlot, GroupSession, 
    InstructorReview, CreditTransaction
)

# Import content app models if available
try:
    from apps.content.models import PrivateSession as ContentPrivateSession
    from apps.content.models import GroupSession as ContentGroupSession
    CONTENT_APP_AVAILABLE = True
except ImportError:
    CONTENT_APP_AVAILABLE = False



# For the credit purchase form
from django import forms


class BookPrivateSessionView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return hasattr(self.request.user, 'is_student') and self.request.user.is_student
    
    def get_credit_balance(self, user):
        """Calculate user's current credit balance"""
        transactions = CreditTransaction.objects.filter(student=user)
        
        # Calculate credits from purchases and refunds
        credits = transactions.filter(
            transaction_type__in=['purchase', 'refund', 'bonus']
        ).aggregate(models.Sum('amount'))['amount__sum'] or 0
        
        # Calculate debits from deductions
        debits = transactions.filter(
            transaction_type='deduction'
        ).aggregate(models.Sum('amount'))['amount__sum'] or 0
        
        return credits - debits

    def post(self, request, slot_id):
        slot = get_object_or_404(PrivateSessionSlot, id=slot_id, status='available')
        
        # Check credit balance
        credit_balance = self.get_credit_balance(request.user)
        
        # Private sessions require 2 credits
        required_credits = 2
        
        if credit_balance < required_credits:
            messages.error(request, f"Insufficient credits. Private sessions require {required_credits} credits. Please purchase credits before booking.")
            return redirect('booking:purchase_credits')
        
        # Proceed with booking and deduct credits
        success, message = slot.book(request.user)
        
        if success:
            CreditTransaction.objects.create(
                student=request.user,
                amount=required_credits,  # Deduct 2 credits for private session
                description=f"Private session with {slot.instructor.user.username}",
                transaction_type='deduction',
                private_session=slot
            )
            messages.success(request, "Session booked successfully!")
        else:
            messages.error(request, message)
        
        return redirect('booking:my_sessions')

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
    
    def get_credit_balance(self, user):
        """Calculate user's current credit balance"""
        transactions = CreditTransaction.objects.filter(student=user)
        
        # Calculate credits from purchases and refunds
        credits = transactions.filter(
            transaction_type__in=['purchase', 'refund', 'bonus']
        ).aggregate(models.Sum('amount'))['amount__sum'] or 0
        
        # Calculate debits from deductions
        debits = transactions.filter(
            transaction_type='deduction'
        ).aggregate(models.Sum('amount'))['amount__sum'] or 0
        
        return credits - debits
    
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
        credit_balance = self.get_credit_balance(request.user)
        
        # Group sessions require 1 credit
        required_credits = 1
        
        # Check if student has enough credits
        if credit_balance < required_credits:
            messages.error(request, f"Insufficient credits. Group sessions require {required_credits} credit. Please purchase credits before enrolling.")
            return redirect('booking:purchase_credits')
        
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
        
        # Check if student has enough credits (1 credit for group session)
        credit_balance = self.get_credit_balance(request.user)
        required_credits = 1
        
        if credit_balance < required_credits:
            messages.error(request, f"You don't have enough credits to enroll in this session. Group sessions require {required_credits} credit.")
            return redirect('booking:purchase_credits')
        
        # Enroll in the session
        success, message = session.enroll_student(request.user)
        
        if success:
            # Deduct 1 credit
            CreditTransaction.objects.create(
                student=request.user,
                amount=required_credits,
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
    template_name = 'dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))

        user = self.request.user
        now = timezone.now()

        # Different views depending on user type
        if hasattr(user, 'is_teacher') and user.is_teacher:
            # Teacher/instructor view
            if hasattr(user, 'booking_instructor_profile'):
                instructor = user.booking_instructor_profile

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
                ).order_by('start_time')

                # Stats for the cards
                context['total_slots'] = PrivateSessionSlot.objects.filter(
                    instructor=instructor
                ).count()

                context['total_booked'] = PrivateSessionSlot.objects.filter(
                    instructor=instructor,
                    status='booked'
                ).count()

                context['total_completed'] = PrivateSessionSlot.objects.filter(
                    instructor=instructor,
                    status='completed'
                ).count()

            # Set active menu attributes
            context['is_teacher'] = True
            context['active_menu'] = 'booking'
            context['active_submenu'] = 'instructor_booking'

        else:
            # Student view
            # Get upcoming private sessions from booking app
            context['my_bookings'] = PrivateSessionSlot.objects.filter(
                student=user,
                status='booked',
                start_time__gt=now
            ).order_by('start_time')

            # Get upcoming group sessions from booking app
            group_bookings = GroupSession.objects.filter(
                students=user,
                status='scheduled',
                start_time__gt=now
            ).count()

            # Count total upcoming sessions
            context['upcoming_sessions'] = context['my_bookings'].count() + group_bookings

            # Get student's credit balance
            credit_balance = 0
            if CreditTransaction.objects.filter(student=user).exists():
                transactions = CreditTransaction.objects.filter(student=user)

                # Calculate credits from purchases and refunds
                credits = transactions.filter(
                    transaction_type__in=['purchase', 'refund', 'bonus']
                ).aggregate(models.Sum('amount'))['amount__sum'] or 0

                # Calculate debits from deductions
                debits = transactions.filter(
                    transaction_type='deduction'
                ).aggregate(models.Sum('amount'))['amount__sum'] or 0

                credit_balance = credits - debits

            context['credit_balance'] = credit_balance

            # Get available instructors for booking
            context['available_instructors'] = Instructor.objects.filter(
                is_available=True
            ).select_related('user')[:4]

            # Get available private session slots from booking app
            available_private_slots = PrivateSessionSlot.objects.filter(
                status='available',
                start_time__gt=now
            ).select_related('instructor', 'instructor__user').order_by('start_time')

            # Get available group sessions from booking app
            available_group_sessions = GroupSession.objects.filter(
                status='scheduled',
                start_time__gt=now
            ).select_related('instructor', 'instructor__user').order_by('start_time')

            # Check if content app is available
            try:
                from apps.content.models import PrivateSession as ContentPrivateSession
                from apps.content.models import GroupSession as ContentGroupSession

                # Get private sessions from content app
                content_private_sessions = ContentPrivateSession.objects.filter(
                    status='available',
                    start_time__gt=now
                ).select_related('instructor', 'instructor__user').order_by('start_time')

                # Get group sessions from content app
                content_group_sessions = ContentGroupSession.objects.filter(
                    status='scheduled',
                    start_time__gt=now
                ).select_related('instructor', 'instructor__user').order_by('start_time')

                # Convert querysets to lists for easier manipulation
                context['available_private_slots'] = list(available_private_slots) + list(content_private_sessions)
                context['available_group_sessions'] = list(available_group_sessions) + list(content_group_sessions)
            except (ImportError, AttributeError):
                # Content app not available or models not compatible
                context['available_private_slots'] = available_private_slots
                context['available_group_sessions'] = available_group_sessions

            # Apply language filter if specified
            language = self.request.GET.get('language')
            if language:
                context['available_private_slots'] = [s for s in context['available_private_slots'] if s.language == language]
                context['available_group_sessions'] = [s for s in context['available_group_sessions'] if s.language == language]

            # Set active menu attributes
            context['is_teacher'] = False
            context['active_menu'] = 'booking'
            context['active_submenu'] = 'student_booking'

            # Current time for template use
            context['now'] = now

        # Set the layout path
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)

        return context

class BookPrivateSessionView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return hasattr(self.request.user, 'is_student') and self.request.user.is_student
    
    def get_credit_balance(self, user):
        """Calculate user's current credit balance"""
        transactions = CreditTransaction.objects.filter(student=user)
        
        # Calculate credits from purchases and refunds
        credits = transactions.filter(
            transaction_type__in=['purchase', 'refund', 'bonus']
        ).aggregate(total=models.Sum('amount'))['total'] or 0
        
        # Calculate debits from deductions
        debits = transactions.filter(
            transaction_type='deduction'
        ).aggregate(total=models.Sum('amount'))['total'] or 0
        
        return credits - debits

    def get(self, request, slot_id):
        # Check if this is a slot from booking app or content app
        try:
            slot = PrivateSessionSlot.objects.get(id=slot_id, status='available')
            from_content_app = False
        except PrivateSessionSlot.DoesNotExist:
            # Try to get from content app
            slot = get_object_or_404(PrivateSession, id=slot_id, status='available')
            from_content_app = True
        
        # Get credit balance
        credit_balance = self.get_credit_balance(request.user)
        
        # Check if user has enough credits (2 required for private session)
        if credit_balance < 2:
            return render(request, 'insufficient_credits.html', {
                'credit_balance': credit_balance,
                'required_credits': 2,
                'slot': slot,
                'session_type': 'private',
                'active_menu': 'booking',
                'active_submenu': 'dashboard',
                'layout_path': TemplateHelper.set_layout("layout_vertical.html")
            })
        
        return render(request, 'book_slot.html', {
            'slot': slot,
            'from_content_app': from_content_app,
            'credit_balance': credit_balance,
            'required_credits': 2,
            'active_menu': 'booking',
            'active_submenu': 'dashboard',
            'layout_path': TemplateHelper.set_layout("layout_vertical.html")
        })

    def post(self, request, slot_id):
        # Check if this is a slot from booking app or content app
        try:
            slot = PrivateSessionSlot.objects.get(id=slot_id, status='available')
            from_content_app = False
        except PrivateSessionSlot.DoesNotExist:
            # Try to get from content app
            slot = get_object_or_404(PrivateSession, id=slot_id, status='available')
            from_content_app = True
        
        # Check credit balance
        credit_balance = self.get_credit_balance(request.user)
        
        # 2 credits required for private sessions
        if credit_balance < 2:
            messages.error(request, "Insufficient credits. You need 2 credits for a private session.")
            return redirect('booking:purchase_credits')
        
        # Proceed with booking and deduct credits
        if from_content_app:
            # Handle booking in content app
            slot.mark_as_booked(request.user)
            success = True
        else:
            # Handle booking in booking app
            success, message = slot.book(request.user)
        
        if success:
            # Create credit transaction (deduct 2 credits)
            if from_content_app:
                CreditTransaction.objects.create(
                    student=request.user,
                    amount=2,  # 2 credits for private session
                    description=f"Private session with {slot.instructor.user.username}",
                    transaction_type='deduction',
                )
            else:
                CreditTransaction.objects.create(
                    student=request.user,
                    amount=2,  # 2 credits for private session
                    description=f"Private session with {slot.instructor.user.username}",
                    transaction_type='deduction',
                    private_session=slot
                )
            messages.success(request, "Session booked successfully!")
        else:
            messages.error(request, message if 'message' in locals() else "Failed to book session.")
        
        return redirect('booking:my_sessions')


class EnrollGroupSessionView(LoginRequiredMixin, UserPassesTestMixin, View):
    """View to enroll in a group session"""
    
    def test_func(self):
        return hasattr(self.request.user, 'is_student') and self.request.user.is_student
    
    def get(self, request, session_id):
        # Check if this session is from booking app or content app
        try:
            session = GroupSession.objects.get(id=session_id, status='scheduled')
            from_content_app = False
        except GroupSession.DoesNotExist:
            # Try to get from content app
            session = get_object_or_404(GroupSession, id=session_id, status='scheduled')
            from_content_app = True
        
        # Check if already enrolled
        if from_content_app:
            already_enrolled = request.user in session.students.all()
        else:
            already_enrolled = session.students.filter(id=request.user.id).exists()
            
        if already_enrolled:
            messages.info(request, "You are already enrolled in this session.")
            return redirect('content:group_session_detail', session_id=session.id) if from_content_app else redirect('booking:dashboard')
        
        # Check if session is full
        if session.is_full:
            messages.error(request, "This session is full.")
            return redirect('content:group_session_detail', session_id=session.id) if from_content_app else redirect('booking:dashboard')
        
        # Get student's credit balance
        credit_balance = 0
        if CreditTransaction.objects.filter(student=request.user).exists():
            last_transaction = CreditTransaction.objects.filter(student=request.user).latest('created_at')
            credit_balance = last_transaction.get_balance()
        
        # Check if user has enough credits (1 required for group session)
        if credit_balance < 1:
            return render(request, 'insufficient_credits.html', {
                'credit_balance': credit_balance,
                'required_credits': 1,
                'session': session,
                'session_type': 'group',
                'active_menu': 'booking',
                'active_submenu': 'dashboard',
                'layout_path': TemplateHelper.set_layout("layout_vertical.html")
            })
        
        return render(request, 'enroll_group_session.html', {
            'session': session,
            'instructor': session.instructor,
            'credit_balance': credit_balance,
            'required_credits': 1,
            'from_content_app': from_content_app,
            'active_menu': 'booking',
            'active_submenu': 'group_sessions',
            'layout_path': TemplateHelper.set_layout("layout_vertical.html")
        })
    
    def post(self, request, session_id):
        # Check if this session is from booking app or content app
        try:
            session = GroupSession.objects.get(id=session_id, status='scheduled')
            from_content_app = False
        except GroupSession.DoesNotExist:
            # Try to get from content app
            session = get_object_or_404(GroupSession, id=session_id, status='scheduled')
            from_content_app = True
        
        # Check if session is full
        if session.is_full:
            messages.error(request, "This session is full.")
            return redirect('content:group_session_detail', session_id=session.id) if from_content_app else redirect('booking:dashboard')
        
        # Check if student has enough credits (1 credit for group session)
        credit_balance = 0
        if CreditTransaction.objects.filter(student=request.user).exists():
            last_transaction = CreditTransaction.objects.filter(student=request.user).latest('created_at')
            credit_balance = last_transaction.get_balance()
        
        if credit_balance < 1:
            messages.error(request, "You don't have enough credits to enroll in this session.")
            return redirect('booking:purchase_credits')
        
        # Enroll in the session
        if from_content_app:
            # Use the content app enrollment method
            success = True
            session.students.add(request.user)
            message = "Successfully enrolled in the group session!"
        else:
            # Use the booking app enrollment method
            success, message = session.enroll_student(request.user)
        
        if success:
            # Deduct credits (1 credit for group session)
            if from_content_app:
                CreditTransaction.objects.create(
                    student=request.user,
                    amount=1,  # 1 credit for group session
                    description=f"Enrollment in group session '{session.title}' on {session.start_time}",
                    transaction_type='deduction',
                )
            else:
                CreditTransaction.objects.create(
                    student=request.user,
                    amount=1,  # 1 credit for group session
                    description=f"Enrollment in group session '{session.title}' on {session.start_time}",
                    transaction_type='deduction',
                    group_session=session
                )
            
            messages.success(request, "Successfully enrolled in the group session!")
            return redirect('content:group_session_detail', session_id=session.id) if from_content_app else redirect('booking:my_sessions')
        else:
            messages.error(request, message)
            return redirect('content:group_session_detail', session_id=session.id) if from_content_app else redirect('booking:dashboard')

class MySessionsView(LoginRequiredMixin, TemplateView):
    """View for students to see all their booked sessions"""
    template_name = 'my_sessions.html'
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        user = self.request.user
        now = timezone.now()
        
        # Determine if user is student or instructor
        is_student = hasattr(user, 'is_student') and user.is_student
        is_instructor = hasattr(user, 'is_teacher') and user.is_teacher and hasattr(user, 'instructor_profile')
        
        if is_student:
            # Private sessions from booking app
            upcoming_private_sessions = PrivateSessionSlot.objects.filter(
                student=user,
                status='booked',
                start_time__gt=now
            ).order_by('start_time')
            
            past_private_sessions = PrivateSessionSlot.objects.filter(
                student=user,
                start_time__lt=now
            ).order_by('-start_time')[:10]
            
            # Group sessions from booking app
            upcoming_group_sessions = GroupSession.objects.filter(
                students=user,
                status='scheduled',
                start_time__gt=now
            ).order_by('start_time')
            
            past_group_sessions = GroupSession.objects.filter(
                students=user,
                start_time__lt=now
            ).order_by('-start_time')[:10]
            
            # Try to get sessions from content app
            try:
                from apps.content.models import PrivateSession as ContentPrivateSession
                from apps.content.models import GroupSession as ContentGroupSession
                
                # Private sessions from content app
                content_upcoming_private = ContentPrivateSession.objects.filter(
                    student=user,
                    status='booked',
                    start_time__gt=now
                ).order_by('start_time')
                
                content_past_private = ContentPrivateSession.objects.filter(
                    student=user,
                    start_time__lt=now
                ).order_by('-start_time')[:10]
                
                # Group sessions from content app
                content_upcoming_group = ContentGroupSession.objects.filter(
                    students=user,
                    status='scheduled',
                    start_time__gt=now
                ).order_by('start_time')
                
                content_past_group = ContentGroupSession.objects.filter(
                    students=user,
                    start_time__lt=now
                ).order_by('-start_time')[:10]
                
                # Combine the results
                context['upcoming_private_sessions'] = list(upcoming_private_sessions) + list(content_upcoming_private)
                context['past_private_sessions'] = list(past_private_sessions) + list(content_past_private)
                context['upcoming_group_sessions'] = list(upcoming_group_sessions) + list(content_upcoming_group)
                context['past_group_sessions'] = list(past_group_sessions) + list(content_past_group)
                
                # Sort combined lists
                context['upcoming_private_sessions'].sort(key=lambda x: x.start_time)
                context['past_private_sessions'].sort(key=lambda x: x.start_time, reverse=True)
                context['upcoming_group_sessions'].sort(key=lambda x: x.start_time)
                context['past_group_sessions'].sort(key=lambda x: x.start_time, reverse=True)
                
            except (ImportError, AttributeError):
                # Content app not available or models not compatible
                context['upcoming_private_sessions'] = upcoming_private_sessions
                context['past_private_sessions'] = past_private_sessions
                context['upcoming_group_sessions'] = upcoming_group_sessions
                context['past_group_sessions'] = past_group_sessions
            
            # Credit balance
            credit_balance = 0
            if CreditTransaction.objects.filter(student=user).exists():
                transactions = CreditTransaction.objects.filter(student=user)
                credits = transactions.filter(
                    transaction_type__in=['purchase', 'refund', 'bonus']
                ).aggregate(models.Sum('amount'))['amount__sum'] or 0
                
                debits = transactions.filter(
                    transaction_type='deduction'
                ).aggregate(models.Sum('amount'))['amount__sum'] or 0
                
                credit_balance = credits - debits
            
            context['credit_balance'] = credit_balance
            
            # Show the student view
            context['is_student_view'] = True
            
        elif is_instructor:
            # Set instructor context here if needed
            # (Most instructors would use the instructor dashboard in content app)
            context['is_student_view'] = False
        
        # Set active menu attributes
        context['active_menu'] = 'booking'
        context['active_submenu'] = 'my_sessions'
        
        # Set the layout path
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context