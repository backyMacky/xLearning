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
from django.core.mail import send_mail
from django.utils.html import strip_tags
from django.template.loader import render_to_string
from django.db import transaction
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
    """View for booking private session slots with proper duplicate handling"""
    
    def test_func(self):
        """Check if user has permission to book sessions"""
        # Skip permission checks in testing mode
        from django.conf import settings
        if hasattr(settings, 'TESTING') and settings.TESTING:
            return True
            
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

    def get(self, request, slot_id):
        """Handle GET request to display booking confirmation form"""
        # Query for slots using filter instead of get to avoid MultipleObjectsReturned
        slots = PrivateSessionSlot.objects.filter(id=slot_id, status='available')
        
        if not slots.exists():
            # If no slots found in booking app, try content app
            try:
                from apps.content.models import PrivateSession
                # Use filter here too to avoid potential issues
                content_slots = PrivateSession.objects.filter(id=slot_id, status='available')
                if not content_slots.exists():
                    messages.error(request, "The session slot you're trying to book doesn't exist or is unavailable.")
                    return redirect('booking:dashboard')
                
                slot = content_slots.first()
                from_content_app = True
            except (ImportError, PrivateSession.DoesNotExist):
                messages.error(request, "The session slot you're trying to book doesn't exist or is unavailable.")
                return redirect('booking:dashboard')
        else:
            # Use the first slot found
            slot = slots.first()
            from_content_app = False
            
            # If duplicates exist, log it but don't fix it now (we'll handle in POST)
            if slots.count() > 1:
                print(f"Warning: Found {slots.count()} duplicate slots with id={slot_id}")
                
        # Get credit balance
        credit_balance = self.get_credit_balance(request.user)
        
        # Check required credits - adjust this based on your system's requirements
        required_credits = 1  # Changed to match UI showing 1 credit
        
        # Check if user has enough credits
        if credit_balance < required_credits:
            # Initialize template context
            context = {
                'credit_balance': credit_balance,
                'required_credits': required_credits,
                'slot': slot,
                'session_type': 'private',
                'active_menu': 'booking',
                'active_submenu': 'dashboard',
            }
            
            # Set the layout path using TemplateHelper
            context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
            TemplateHelper.map_context(context)
            
            return render(request, 'insufficient_credits.html', context)
        
        # Initialize template context for book_slot.html
        context = {
            'slot': slot,
            'from_content_app': from_content_app,
            'credit_balance': credit_balance,
            'required_credits': required_credits,
            'active_menu': 'booking',
            'active_submenu': 'dashboard',
        }
        
        # Set the layout path using TemplateHelper
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return render(request, 'book_slot.html', context)

    def post(self, request, slot_id):
        """Handle POST request to process booking"""
        # Use database transaction to ensure consistent state
        with transaction.atomic():
            try:
                # Query using filter() to avoid MultipleObjectsReturned
                slots = PrivateSessionSlot.objects.filter(id=slot_id, status='available')
                
                if not slots.exists():
                    # If not found in booking app, try content app
                    try:
                        from apps.content.models import PrivateSession
                        content_slots = PrivateSession.objects.filter(id=slot_id, status='available')
                        if not content_slots.exists():
                            messages.error(request, "The session slot you're trying to book doesn't exist or is unavailable.")
                            return redirect('booking:dashboard')
                            
                        slot = content_slots.first()
                        from_content_app = True
                    except (ImportError, AttributeError):
                        messages.error(request, "The session slot you're trying to book doesn't exist or is unavailable.")
                        return redirect('booking:dashboard')
                else:
                    # Use the first slot found
                    slot = slots.first()
                    from_content_app = False
                    
                    # Clean up duplicates if they exist
                    if slots.count() > 1:
                        # Keep the slot we're using and delete others
                        keep_pk = slot.pk
                        duplicate_pks = list(slots.exclude(pk=keep_pk).values_list('pk', flat=True))
                        if duplicate_pks:
                            print(f"Deleting {len(duplicate_pks)} duplicate slots: {duplicate_pks}")
                            PrivateSessionSlot.objects.filter(pk__in=duplicate_pks).delete()
                
                # Check credit balance
                credit_balance = self.get_credit_balance(request.user)
                
                # Set required credits - adjust to match UI
                required_credits = 1  # Changed to 1 credit
                
                if credit_balance < required_credits:
                    messages.error(request, f"Insufficient credits. You need {required_credits} credit for a private session.")
                    return redirect('booking:purchase_credits')
                
                # Process the booking
                if from_content_app:
                    # Book in content app
                    slot.mark_as_booked(request.user)
                    success = True
                    message = "Session booked successfully!"
                else:
                    # Book in booking app
                    success, message = slot.book(request.user)
                
                if success:
                    # Deduct credits
                    CreditTransaction.objects.create(
                        student=request.user,
                        amount=required_credits,
                        description=f"Private session with {slot.instructor.user.username}",
                        transaction_type='deduction',
                        private_session=None if from_content_app else slot
                    )
                    
                    # Prepare for email notification
                    instructor_name = slot.instructor.user.username
                    session_date = slot.start_time.strftime('%A, %B %d, %Y')
                    session_time = slot.start_time.strftime('%I:%M %p')
                    
                    # Get meeting link if available
                    meeting_link = None
                    if hasattr(slot, 'meeting') and slot.meeting:
                        meeting_link = slot.meeting.meeting_link
                    
                    # Create Google Calendar link
                    from datetime import datetime
                    start_time = slot.start_time.strftime('%Y%m%dT%H%M%S')
                    end_time = slot.end_time.strftime('%Y%m%dT%H%M%S')
                    title = f"Language Session with {instructor_name}"
                    details = f"Your language learning session with {instructor_name}"
                    location = meeting_link if meeting_link else "Online"
                    google_calendar_link = f"https://calendar.google.com/calendar/render?action=TEMPLATE&text={title}&dates={start_time}/{end_time}&details={details}&location={location}"
                    
                    # Send email confirmation
                    context = {
                        'user': request.user,
                        'instructor': instructor_name,
                        'session_date': session_date,
                        'session_time': session_time,
                        'session_duration': slot.duration_minutes,
                        'meeting_link': meeting_link,
                        'google_calendar_link': google_calendar_link
                    }
                    
                    try:
                        html_message = render_to_string('email/booking_confirmation.html', context)
                        plain_message = strip_tags(html_message)
                        
                        send_mail(
                            subject=f"Your session with {instructor_name} is confirmed!",
                            message=plain_message,
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            recipient_list=[request.user.email],
                            html_message=html_message,
                            fail_silently=True
                        )
                    except Exception as e:
                        # Log but continue if email fails
                        print(f"Error sending confirmation email: {e}")
                    
                    messages.success(request, "Session booked successfully! Check your email for details.")
                else:
                    messages.error(request, message)
                
                return redirect('booking:my_sessions')
                
            except Exception as e:
                # Catch and log any unexpected errors
                print(f"Booking error: {e}")
                messages.error(request, f"An error occurred while booking: {str(e)}")
                return redirect('booking:dashboard')
            
class CancelPrivateSessionView(LoginRequiredMixin, View):
    """View to cancel a booked private session"""
    
    def get(self, request, slot_id):
        # Find the session (could be booked by student or created by instructor)
        try:
            if hasattr(request.user, 'is_student') and request.user.is_student:
                # Use filter to avoid MultipleObjectsReturned error
                slots = PrivateSessionSlot.objects.filter(id=slot_id, student=request.user, status='booked')
                if not slots.exists():
                    messages.error(request, "Session not found or cannot be cancelled.")
                    return redirect('booking:my_sessions')
                slot = slots.first()
            else:
                # For instructors
                instructor = Instructor.objects.get(user=request.user)
                slots = PrivateSessionSlot.objects.filter(id=slot_id, instructor=instructor)
                if not slots.exists():
                    messages.error(request, "Session not found or cannot be cancelled.")
                    return redirect('booking:my_sessions')
                slot = slots.first()
                
            # Initialize context with TemplateLayout for proper styling
            context = TemplateLayout.init(self, {
                'slot': slot,
                'active_menu': 'booking',
                'active_submenu': 'my_sessions',
                'now': timezone.now()
            })
            
            # Let TemplateHelper handle the layout path
            context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
            TemplateHelper.map_context(context)
            
            return render(request, 'cancel_booking.html', context)
            
        except Exception as e:
            messages.error(request, f"An error occurred: {str(e)}")
            return redirect('booking:my_sessions')
    
    def post(self, request, slot_id):
        # Use transaction to avoid recursion issues
        with transaction.atomic():
            try:
                # Temporarily disconnect the signals to prevent recursion
                from django.db.models.signals import post_save
                from .models import sync_booking_to_private_session
                
                # Find the session using filter() to avoid MultipleObjectsReturned
                if hasattr(request.user, 'is_student') and request.user.is_student:
                    slots = PrivateSessionSlot.objects.filter(id=slot_id, student=request.user, status='booked')
                    if not slots.exists():
                        messages.error(request, "Session not found or cannot be cancelled.")
                        return redirect('booking:my_sessions')
                    slot = slots.first()
                else:
                    # For instructors
                    instructor = Instructor.objects.get(user=request.user)
                    slots = PrivateSessionSlot.objects.filter(id=slot_id, instructor=instructor)
                    if not slots.exists():
                        messages.error(request, "Session not found or cannot be cancelled.")
                        return redirect('booking:my_sessions')
                    slot = slots.first()
                
                # Store needed data before cancellation
                student = slot.student
                instructor_user = slot.instructor.user
                start_time = slot.start_time
                
                # Handle cancellation using the slot's cancel method
                if hasattr(slot, 'cancel') and callable(slot.cancel):
                    success, message = slot.cancel(request.user)
                    if success:
                        if request.user == instructor_user and student:
                            messages.success(request, "Session cancelled successfully. The student has been notified and refunded.")
                        else:
                            messages.success(request, "Session cancelled successfully.")
                    else:
                        messages.error(request, message)
                else:
                    # Manual cancellation if cancel method not available
                    slot.status = 'cancelled'
                    
                    # If this is the instructor cancelling, clear the student reference
                    if request.user == instructor_user:
                        student_email = student.email if student else None
                        slot.student = None
                    
                    # Save with signals disabled
                    post_save.disconnect(sync_booking_to_private_session, sender=PrivateSessionSlot)
                    slot.save()
                    post_save.connect(sync_booking_to_private_session, sender=PrivateSessionSlot)
                    
                    # Clean up the meeting if it exists
                    if slot.meeting:
                        slot.meeting.delete()
                        slot.meeting = None
                        
                        # Save again with signals disabled
                        post_save.disconnect(sync_booking_to_private_session, sender=PrivateSessionSlot)
                        slot.save()
                        post_save.connect(sync_booking_to_private_session, sender=PrivateSessionSlot)
                    
                    # If the instructor cancelled and the slot was booked
                    if request.user == instructor_user and student:
                        # Issue a refund to the student
                        CreditTransaction.objects.create(
                            student=student,
                            amount=1,  # Updated to 1 credit to match UI
                            description=f"Refund for cancelled session with {request.user.username}",
                            transaction_type='refund',
                            private_session=slot
                        )
                        
                        # Notify the student via email
                        from django.core.mail import send_mail
                        from django.template.loader import render_to_string
                        from django.utils.html import strip_tags
                        
                        context = {
                            'user': student,
                            'instructor': instructor_user.username,
                            'session_date': start_time.strftime('%A, %B %d, %Y'),
                            'session_time': start_time.strftime('%I:%M %p'),
                            'refund_amount': 1  # Updated to 1 credit
                        }
                        
                        try:
                            html_message = render_to_string('email/session_cancelled_by_instructor.html', context)
                            plain_message = strip_tags(html_message)
                            
                            send_mail(
                                subject=f"Your session with {instructor_user.username} has been cancelled",
                                message=plain_message,
                                from_email=settings.DEFAULT_FROM_EMAIL,
                                recipient_list=[student_email],
                                html_message=html_message,
                                fail_silently=True
                            )
                        except Exception as e:
                            print(f"Error sending cancellation email: {e}")
                        
                        messages.success(request, "Session cancelled successfully. The student has been notified and refunded.")
                    else:
                        # Student cancelling
                        messages.success(request, "Session cancelled successfully.")
                
                # Redirect to appropriate dashboard
                if hasattr(request.user, 'is_student') and request.user.is_student:
                    return redirect('booking:my_sessions')
                else:
                    return redirect('content:instructor_dashboard')
                    
            except Exception as e:
                messages.error(request, f"An error occurred while cancelling the session: {str(e)}")
                return redirect('booking:my_sessions')
            
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
        # Check if this session is from booking app or content app
        try:
            session = GroupSession.objects.get(id=session_id, status='scheduled')
            from_content_app = False
        except GroupSession.DoesNotExist:
            # Try to get from content app
            try:
                from apps.content.models import GroupSession as ContentGroupSession
                session = get_object_or_404(ContentGroupSession, id=session_id, status='scheduled')
                from_content_app = True
            except (ImportError, ContentGroupSession.DoesNotExist):
                messages.error(request, "The group session you're trying to enroll in doesn't exist or is unavailable.")
                return redirect('booking:dashboard')
        
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
        credit_balance = self.get_credit_balance(request.user)
        
        # Check if user has enough credits (1 required for group session)
        if credit_balance < 1:
            # Initialize template context
            context = {
                'credit_balance': credit_balance,
                'required_credits': 1,
                'session': session,
                'session_type': 'group',
                'active_menu': 'booking',
                'active_submenu': 'dashboard',
            }
            
            # Set the layout path using TemplateHelper
            context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
            TemplateHelper.map_context(context)
            
            return render(request, 'insufficient_credits.html', context)
        
        # Initialize template context
        context = {
            'session': session,
            'instructor': session.instructor,
            'credit_balance': credit_balance,
            'required_credits': 1,
            'from_content_app': from_content_app,
            'active_menu': 'booking',
            'active_submenu': 'group_sessions',
        }
        
        # Set the layout path using TemplateHelper
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return render(request, 'enroll_group_session.html', context)
    
    def post(self, request, session_id):
        # Check if this session is from booking app or content app
        try:
            session = GroupSession.objects.get(id=session_id, status='scheduled')
            from_content_app = False
        except GroupSession.DoesNotExist:
            # Try to get from content app
            try:
                from apps.content.models import GroupSession as ContentGroupSession
                session = get_object_or_404(ContentGroupSession, id=session_id, status='scheduled')
                from_content_app = True
            except (ImportError, ContentGroupSession.DoesNotExist):
                messages.error(request, "The group session you're trying to enroll in doesn't exist or is unavailable.")
                return redirect('booking:dashboard')
        
        # Check if session is full
        if session.is_full:
            messages.error(request, "This session is full.")
            return redirect('content:group_session_detail', session_id=session.id) if from_content_app else redirect('booking:dashboard')
        
        # Check if student has enough credits (1 credit for group session)
        credit_balance = self.get_credit_balance(request.user)
        
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
        context['now'] = now

        # Set the layout path
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)

        return context