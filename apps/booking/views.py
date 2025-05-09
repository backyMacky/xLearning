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

class CreateSessionView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Combined view for creating both private and group sessions in the booking app"""
    template_name = 'session_form.html'
    
    def test_func(self):
        """Only users with instructor profiles can create sessions"""
        from django.conf import settings
        if hasattr(settings, 'TESTING') and settings.TESTING:
            return True  # Skip permission checks in testing mode
            
        # Check if user has instructor profile in the booking app
        return hasattr(self.request.user, 'booking_instructor_profile')
    
    def get(self, request):
        # Initialize context with both form types
        from .models import PrivateSessionSlot, GroupSession
        
        # Get session type from URL parameter
        session_type = request.GET.get('type', 'private')
        is_private = session_type != 'group'
        
        # Create simplified forms - get these from your app's form definitions
        from django import forms
        
        class SimplePrivateSessionForm(forms.Form):
            language = forms.ChoiceField(choices=PrivateSessionSlot.LANGUAGE_CHOICES)
            level = forms.ChoiceField(choices=PrivateSessionSlot.LEVEL_CHOICES)
            duration_minutes = forms.ChoiceField(choices=[
                (30, '30 minutes'),
                (45, '45 minutes'),
                (60, '1 hour'),
                (90, '1.5 hours'),
                (120, '2 hours')
            ])
            session_date = forms.DateField(widget=forms.DateInput(attrs={'class': 'flatpickr-date'}))
            session_time = forms.TimeField(widget=forms.TimeInput(attrs={'class': 'flatpickr-time'}))
            
        class SimpleGroupSessionForm(forms.Form):
            title = forms.CharField(max_length=255)
            description = forms.CharField(widget=forms.Textarea)
            language = forms.ChoiceField(choices=GroupSession.LANGUAGE_CHOICES)
            level = forms.ChoiceField(choices=GroupSession.LEVEL_CHOICES)
            duration_minutes = forms.ChoiceField(choices=[
                (30, '30 minutes'),
                (45, '45 minutes'),
                (60, '1 hour'),
                (90, '1.5 hours'),
                (120, '2 hours')
            ])
            max_students = forms.ChoiceField(choices=[
                (5, '5 students'),
                (10, '10 students'),
                (15, '15 students'),
                (20, '20 students'),
                (30, '30 students')
            ])
            min_students = forms.ChoiceField(choices=[
                (1, '1 student (no minimum)'),
                (2, '2 students'),
                (3, '3 students'),
                (5, '5 students')
            ])
            session_date = forms.DateField(widget=forms.DateInput(attrs={'class': 'flatpickr-date'}))
            session_time = forms.TimeField(widget=forms.TimeInput(attrs={'class': 'flatpickr-time'}))
            tags = forms.CharField(required=False)
            
        private_form = SimplePrivateSessionForm()
        group_form = SimpleGroupSessionForm()
        
        context = {
            'private_form': private_form,
            'group_form': group_form,
            'is_private': is_private,
            'is_update': False,
            'title': 'Create Session',
            'active_menu': 'instructor',
            'active_submenu': 'sessions',
            'layout_path': "layout_vertical.html"
        }
        
        return render(request, self.template_name, context)
    
    def post(self, request):
        # Determine which form was submitted
        session_type = request.POST.get('session_type', 'private')
        is_private = session_type != 'group'
        
        if is_private:
            # Process private session form
            from .models import PrivateSessionSlot, Instructor
            from django.utils import timezone
            
            # Get form data
            language = request.POST.get('language')
            level = request.POST.get('level')
            duration_minutes = int(request.POST.get('duration_minutes', 60))
            session_date = request.POST.get('session_date')
            session_time = request.POST.get('session_time')
            is_trial = request.POST.get('is_trial') == 'on'
            
            # Validate form data
            if not all([language, level, session_date, session_time]):
                messages.error(request, "Please fill out all required fields.")
                return redirect('booking:create_session')
            
            # Convert date/time strings to datetime
            import datetime
            try:
                date_obj = datetime.datetime.strptime(session_date, '%Y-%m-%d').date()
                time_obj = datetime.datetime.strptime(session_time, '%H:%M').time()
                start_time = datetime.datetime.combine(date_obj, time_obj)
                start_time = timezone.make_aware(start_time)
                end_time = start_time + timezone.timedelta(minutes=duration_minutes)
            except ValueError:
                messages.error(request, "Invalid date or time format.")
                return redirect('booking:create_session')
            
            # Get or create instructor
            try:
                instructor = Instructor.objects.get(user=request.user)
            except Instructor.DoesNotExist:
                # Create instructor profile if it doesn't exist
                instructor = Instructor.objects.create(
                    user=request.user,
                    bio="",
                    is_available=True
                )
            
            # Create the private session slot
            slot = PrivateSessionSlot.objects.create(
                instructor=instructor,
                start_time=start_time,
                end_time=end_time,
                duration_minutes=duration_minutes,
                language=language,
                level=level,
                status='available'
            )
            
            # Try syncing with content app
            try:
                from apps.content.models import PrivateSession, Instructor as ContentInstructor
                
                # Get or create content instructor
                content_instructor, created = ContentInstructor.objects.get_or_create(
                    user=request.user,
                    defaults={
                        'bio': instructor.bio if hasattr(instructor, 'bio') else '',
                        'hourly_rate': instructor.hourly_rate if hasattr(instructor, 'hourly_rate') else 25.00
                    }
                )
                
                # Create content private session
                PrivateSession.objects.create(
                    instructor=content_instructor,
                    start_time=start_time,
                    end_time=end_time,
                    duration_minutes=duration_minutes,
                    language=language,
                    level=level,
                    status='available',
                    is_trial=is_trial
                )
            except (ImportError, AttributeError) as e:
                # Content app not available or models not compatible
                print(f"Error syncing with content app: {e}")
            
            messages.success(request, "Private session slot created successfully!")
            return redirect('booking:dashboard')
        else:
            # Process group session form
            from .models import GroupSession, Instructor
            from django.utils import timezone
            
            # Get form data
            title = request.POST.get('title')
            description = request.POST.get('description')
            language = request.POST.get('language')
            level = request.POST.get('level')
            duration_minutes = int(request.POST.get('duration_minutes', 60))
            max_students = int(request.POST.get('max_students', 5))
            min_students = int(request.POST.get('min_students', 2))
            session_date = request.POST.get('session_date')
            session_time = request.POST.get('session_time')
            tags = request.POST.get('tags', '')
            
            # Validate form data
            if not all([title, description, language, level, session_date, session_time]):
                messages.error(request, "Please fill out all required fields.")
                return redirect('booking:create_session')
            
            # Convert date/time strings to datetime
            import datetime
            try:
                date_obj = datetime.datetime.strptime(session_date, '%Y-%m-%d').date()
                time_obj = datetime.datetime.strptime(session_time, '%H:%M').time()
                start_time = datetime.datetime.combine(date_obj, time_obj)
                start_time = timezone.make_aware(start_time)
                end_time = start_time + timezone.timedelta(minutes=duration_minutes)
            except ValueError:
                messages.error(request, "Invalid date or time format.")
                return redirect('booking:create_session')
            
            # Get or create instructor
            try:
                instructor = Instructor.objects.get(user=request.user)
            except Instructor.DoesNotExist:
                # Create instructor profile if it doesn't exist
                instructor = Instructor.objects.create(
                    user=request.user,
                    bio="",
                    is_available=True
                )
            
            # Create the group session
            session = GroupSession.objects.create(
                title=title,
                instructor=instructor,
                description=description,
                language=language,
                level=level,
                start_time=start_time,
                end_time=end_time,
                duration_minutes=duration_minutes,
                max_students=max_students,
                min_students=min_students,
                price=15.00,  # Default price
                status='scheduled'
            )
            
            # Try syncing with content app
            try:
                from apps.content.models import GroupSession as ContentGroupSession, Instructor as ContentInstructor
                
                # Get or create content instructor
                content_instructor, created = ContentInstructor.objects.get_or_create(
                    user=request.user,
                    defaults={
                        'bio': instructor.bio if hasattr(instructor, 'bio') else '',
                        'hourly_rate': instructor.hourly_rate if hasattr(instructor, 'hourly_rate') else 25.00
                    }
                )
                
                # Create content group session
                ContentGroupSession.objects.create(
                    title=title,
                    instructor=content_instructor,
                    description=description,
                    language=language,
                    level=level,
                    start_time=start_time,
                    end_time=end_time,
                    duration_minutes=duration_minutes,
                    max_students=max_students,
                    price=15.00,  # Default price
                    status='scheduled',
                    tags=tags
                )
            except (ImportError, AttributeError) as e:
                # Content app not available or models not compatible
                print(f"Error syncing with content app: {e}")
            
            messages.success(request, "Group session created successfully!")
            return redirect('booking:dashboard')

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
        
        # Sum credits from purchases and refunds
        credits = transactions.filter(
            transaction_type__in=['purchase', 'refund', 'bonus']
        ).aggregate(models.Sum('amount'))['amount__sum'] or 0
        
        # Subtract deductions
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
        
        # UPDATED: Check required credits - Private sessions cost 2 credits
        required_credits = 2
        credit_price_usd = 3  # 1 credit = $3 USD
        session_price_usd = required_credits * credit_price_usd  # $6 USD
        
        # Check if user has enough credits
        if credit_balance < required_credits:
            # Initialize template context
            context = {
                'credit_balance': credit_balance,
                'required_credits': required_credits,
                'credit_price_usd': credit_price_usd,
                'session_price_usd': session_price_usd,
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
            'credit_price_usd': credit_price_usd,
            'session_price_usd': session_price_usd,
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
                
                # UPDATED: Check credit balance and required credits
                credit_balance = self.get_credit_balance(request.user)
                required_credits = 2  # Private sessions cost 2 credits
                
                if credit_balance < required_credits:
                    messages.error(request, f"Insufficient credits. You need {required_credits} credits (${required_credits * 3} USD) for a private session.")
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
                    # Deduct credits (2 for private session)
                    CreditTransaction.objects.create(
                        student=request.user,
                        amount=required_credits,
                        description=f"Private session with {slot.instructor.user.username} (${required_credits * 3} USD)",
                        transaction_type='deduction',
                        private_session=None if from_content_app else slot
                    )
                    
                    # Send booking confirmation email
                    try:
                        from .utilities import send_booking_confirmation_email
                        send_booking_confirmation_email(slot, request.user)
                    except Exception as e:
                        # Log but continue if email fails
                        print(f"Error sending booking confirmation email: {e}")
                    
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
        
        # UPDATED: Check if user has enough credits (1 credit required for group session)
        required_credits = 1  # Group sessions cost 1 credit
        credit_price_usd = 3  # 1 credit = $3 USD
        session_price_usd = required_credits * credit_price_usd  # $3 USD
        
        if credit_balance < required_credits:
            # Initialize template context
            context = {
                'credit_balance': credit_balance,
                'required_credits': required_credits,
                'credit_price_usd': credit_price_usd,
                'session_price_usd': session_price_usd,
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
            'required_credits': required_credits,
            'credit_price_usd': credit_price_usd,
            'session_price_usd': session_price_usd,
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
        
        # UPDATED: Check if student has enough credits and setup pricing
        credit_balance = self.get_credit_balance(request.user)
        required_credits = 1  # Group sessions cost 1 credit
        credit_price_usd = 3  # $3 USD per credit
        session_price_usd = required_credits * credit_price_usd  # $3 USD total
        
        if credit_balance < required_credits:
            messages.error(request, f"You don't have enough credits to enroll in this session. You need {required_credits} credit (${session_price_usd} USD).")
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
            CreditTransaction.objects.create(
                student=request.user,
                amount=required_credits,
                description=f"Enrollment in group session '{session.title}' (${session_price_usd} USD)",
                transaction_type='deduction',
                group_session=None if from_content_app else session
            )
            
            # Send booking confirmation email
            try:
                from .utilities import send_booking_confirmation_email
                send_booking_confirmation_email(session, request.user)
            except Exception as e:
                # Log but continue if email fails
                print(f"Error sending booking confirmation email: {e}")
            
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
    """Form for purchasing credits ($3 USD per credit)"""
    CREDIT_CHOICES = [
        (5, '5 Credits - $15'),
        (10, '10 Credits - $30'),
        (20, '20 Credits - $60'),
        (50, '50 Credits - $150'),
    ]
    
    PAYMENT_CHOICES = [
        ('credit_card', 'Credit Card'),
        ('debit_card', 'Debit Card'),
        ('master_card', 'Master Card'),
        ('paypal', 'PayPal'),
    ]
    
    credit_package = forms.ChoiceField(
        choices=CREDIT_CHOICES,
        widget=forms.RadioSelect(),
        label="Select Credit Package"
    )
    
    payment_method = forms.ChoiceField(
        choices=PAYMENT_CHOICES,
        widget=forms.RadioSelect(),
        label="Payment Method"
    )
    
    # Credit Card Information (for demo purposes only)
    card_number = forms.CharField(
        required=False,
        max_length=19,
        widget=forms.TextInput(attrs={'placeholder': '1234 5678 9012 3456'}),
        label="Card Number"
    )
    
    card_holder = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={'placeholder': 'Name on card'}),
        label="Card Holder"
    )
    
    expiry_date = forms.CharField(
        required=False,
        max_length=5,
        widget=forms.TextInput(attrs={'placeholder': 'MM/YY'}),
        label="Expiry Date"
    )
    
    cvc = forms.CharField(
        required=False,
        max_length=4,
        widget=forms.TextInput(attrs={'placeholder': 'CVC'}),
        label="CVC/CVV"
    )

class PurchaseCreditsView(LoginRequiredMixin, FormView):
    """View for students to purchase credits"""
    template_name = 'purchase_credits.html'
    form_class = PurchaseCreditsForm
    success_url = reverse_lazy('booking:transaction_history')
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        # Get student's current credit balance
        credit_balance = 0
        if CreditTransaction.objects.filter(student=self.request.user).exists():
            # Calculate current balance properly
            transactions = CreditTransaction.objects.filter(student=self.request.user)
            
            # Sum credits from purchases and refunds
            credits = transactions.filter(
                transaction_type__in=['purchase', 'refund', 'bonus']
            ).aggregate(models.Sum('amount'))['amount__sum'] or 0
            
            # Calculate debits from deductions
            debits = transactions.filter(
                transaction_type='deduction'
            ).aggregate(models.Sum('amount'))['amount__sum'] or 0
            
            credit_balance = credits - debits
        
        context['credit_balance'] = credit_balance
        
        # Add pricing information
        credit_price_usd = 3  # $3 USD per credit
        context['credit_price_usd'] = credit_price_usd
        
        # Add precomputed prices for each credit package
        context['package_5_price'] = 15  # 5 * $3
        context['package_10_price'] = 30  # 10 * $3
        context['package_20_price'] = 60  # 20 * $3
        context['package_50_price'] = 150  # 50 * $3
        
        # Add info about session pricing
        context['private_session_credits'] = 2
        context['group_session_credits'] = 1
        context['private_session_price'] = 2 * 3  # $6 USD
        context['group_session_price'] = 1 * 3  # $3 USD
        
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
        payment_method = form.cleaned_data['payment_method']
        
        # In a real application, you would integrate with a payment gateway here
        # For this demo, we'll assume the payment was successful
        
        # Create credit transaction
        CreditTransaction.objects.create(
            student=self.request.user,
            amount=credit_package,
            description=f"Purchase of {credit_package} credits (${credit_package * 3} USD) using {dict(form.fields['payment_method'].choices)[payment_method]}",
            transaction_type='purchase'
        )
        
        messages.success(self.request, f"Successfully purchased {credit_package} credits for ${credit_package * 3} USD!")
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


class CancelBookingView(LoginRequiredMixin, View):
    """View to cancel a booking slot (works for both instructors and students)"""
    template_name = 'cancel_booking.html'
    
    def get(self, request, slot_id):
        """Display cancellation confirmation page"""
        try:
            # Determine if user is student or instructor
            if hasattr(request.user, 'is_student') and request.user.is_student:
                # For students: Get slots they've booked
                slots = PrivateSessionSlot.objects.filter(id=slot_id, student=request.user)
                if not slots.exists():
                    messages.error(request, "Session not found or you don't have permission to cancel it.")
                    return redirect('booking:my_sessions')
                slot = slots.first()
            else:
                # For instructors: Get slots they've created
                try:
                    instructor = Instructor.objects.get(user=request.user)
                    slots = PrivateSessionSlot.objects.filter(id=slot_id, instructor=instructor)
                    if not slots.exists():
                        messages.error(request, "Session not found or you don't have permission to cancel it.")
                        return redirect('booking:dashboard')
                    slot = slots.first()
                except Instructor.DoesNotExist:
                    messages.error(request, "You don't have an instructor profile.")
                    return redirect('booking:dashboard')
            
            # Initialize context
            context = TemplateLayout.init(self, {
                'slot': slot,
                'active_menu': 'booking',
                'active_submenu': 'my_sessions' if hasattr(request.user, 'is_student') and request.user.is_student else 'instructor_booking',
                'now': timezone.now()
            })
            
            # Set the layout path using TemplateHelper
            context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
            TemplateHelper.map_context(context)
            
            # Check if this is a late cancellation (less than 24 hours before)
            is_late_cancellation = (slot.start_time - timezone.now()) < timezone.timedelta(hours=24)
            
            # If it's a student canceling late, use the late cancellation template
            if hasattr(request.user, 'is_student') and request.user.is_student and is_late_cancellation and slot.status == 'booked':
                return render(request, 'late_cancellation.html', context)
            
            return render(request, self.template_name, context)
            
        except Exception as e:
            messages.error(request, f"An error occurred: {str(e)}")
            return redirect('booking:dashboard')
    
    def post(self, request, slot_id):
        """Process cancellation request"""
        # Use transaction to avoid issues with signal handling
        with transaction.atomic():
            try:
                # Temporarily disconnect signals to prevent recursion
                from django.db.models.signals import post_save
                from .models import sync_booking_to_private_session
                
                # Find the session using filter to avoid MultipleObjectsReturned
                if hasattr(request.user, 'is_student') and request.user.is_student:
                    # For students
                    slots = PrivateSessionSlot.objects.filter(id=slot_id, student=request.user)
                    if not slots.exists():
                        messages.error(request, "Session not found or cannot be cancelled.")
                        return redirect('booking:my_sessions')
                    slot = slots.first()
                else:
                    # For instructors
                    try:
                        instructor = Instructor.objects.get(user=request.user)
                        slots = PrivateSessionSlot.objects.filter(id=slot_id, instructor=instructor)
                        if not slots.exists():
                            messages.error(request, "Session not found or cannot be cancelled.")
                            return redirect('booking:dashboard')
                        slot = slots.first()
                    except Instructor.DoesNotExist:
                        messages.error(request, "You don't have an instructor profile.")
                        return redirect('booking:dashboard')
                
                # Store needed data before cancellation
                student = slot.student
                instructor_user = slot.instructor.user
                start_time = slot.start_time
                is_late_cancellation = (start_time - timezone.now()) < timezone.timedelta(hours=24)
                force_cancel = request.POST.get('force_cancel') == 'true'
                
                # Check if this is a student trying to cancel late without force
                if hasattr(request.user, 'is_student') and request.user.is_student and is_late_cancellation and slot.status == 'booked' and not force_cancel:
                    # Redirect to late cancellation page
                    return redirect('booking:late_cancellation', slot_id=slot.id)
                
                # Process the cancellation
                if hasattr(slot, 'cancel') and callable(slot.cancel):
                    success, message = slot.cancel(request.user)
                    if success:
                        if request.user == instructor_user and student:
                            messages.success(request, "Session cancelled successfully. The student has been notified and refunded.")
                        else:
                            # Check if student gets a refund (more than 24h before session or instructor cancelled)
                            if not is_late_cancellation or request.user == instructor_user:
                                messages.success(request, "Session cancelled successfully. You've received a refund of 1 credit.")
                            else:
                                messages.success(request, "Session cancelled successfully. No refund was issued due to late cancellation.")
                    else:
                        messages.error(request, message)
                else:
                    # Manual cancellation fallback
                    slot.status = 'cancelled'
                    
                    # If instructor is cancelling, clear student reference and issue refund
                    if request.user == instructor_user and student:
                        student_email = student.email if student else None
                        was_booked = slot.status == 'booked'
                        slot.student = None
                        
                        # Save with signals disabled to avoid recursion
                        post_save.disconnect(sync_booking_to_private_session, sender=PrivateSessionSlot)
                        slot.save()
                        post_save.connect(sync_booking_to_private_session, sender=PrivateSessionSlot)
                        
                        # Issue refund if the slot was booked
                        if was_booked:
                            CreditTransaction.objects.create(
                                student=student,
                                amount=2,  # 2 credits for private session
                                description=f"Refund for cancelled session with {request.user.username}",
                                transaction_type='refund',
                                private_session=slot
                            )
                            
                            # Email notification
                            try:
                                from .utilities import send_cancellation_email
                                send_cancellation_email(slot, student, refund_amount=2)
                            except Exception as e:
                                print(f"Error sending cancellation email: {e}")
                        
                        messages.success(request, "Session cancelled successfully. The student has been notified and refunded.")
                    else:
                        # Student cancelling
                        # Check if eligible for refund (must be >24h before session)
                        if not is_late_cancellation and slot.status == 'booked':
                            # Issue refund
                            CreditTransaction.objects.create(
                                student=request.user,
                                amount=2,  # 2 credits for private session
                                description=f"Refund for cancelled session with {instructor_user.username}",
                                transaction_type='refund',
                                private_session=slot
                            )
                            messages.success(request, "Session cancelled successfully. You've received a refund of 2 credits.")
                        else:
                            messages.success(request, "Session cancelled successfully. No refund was issued due to late cancellation.")
                        
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
                
                # Sync with content app if available
                try:
                    from apps.content.models import PrivateSession
                    content_sessions = PrivateSession.objects.filter(
                        instructor__user=instructor_user, 
                        start_time=start_time
                    )
                    if content_sessions.exists():
                        content_session = content_sessions.first()
                        content_session.status = 'cancelled'
                        if request.user == instructor_user:
                            content_session.student = None
                        content_session.save()
                except (ImportError, AttributeError):
                    pass
                
                # Redirect to appropriate page
                if hasattr(request.user, 'is_student') and request.user.is_student:
                    return redirect('booking:my_sessions')
                else:
                    return redirect('booking:dashboard')
                
            except Exception as e:
                messages.error(request, f"An error occurred while cancelling the session: {str(e)}")
                if hasattr(request.user, 'is_student') and request.user.is_student:
                    return redirect('booking:my_sessions')
                else:
                    return redirect('booking:dashboard')
                    

class LateCancellationView(LoginRequiredMixin, UserPassesTestMixin, View):
    """View for handling late cancellations (less than 24h before session)"""
    template_name = 'late_cancellation.html'
    
    def test_func(self):
        """Only students can access this view"""
        return hasattr(self.request.user, 'is_student') and self.request.user.is_student
    
    def get(self, request, slot_id):
        """Display late cancellation warning"""
        try:
            # Get the slot
            slot = get_object_or_404(PrivateSessionSlot, id=slot_id, student=request.user, status='booked')
            
            # Verify this is actually a late cancellation
            if (slot.start_time - timezone.now()) >= timezone.timedelta(hours=24):
                # Not a late cancellation, redirect to regular cancellation
                return redirect('booking:cancel_booking', slot_id=slot.id)
            
            # Initialize context
            context = TemplateLayout.init(self, {
                'slot': slot,
                'active_menu': 'booking',
                'active_submenu': 'my_sessions',
                'now': timezone.now()
            })
            
            # Set the layout path using TemplateHelper
            context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
            TemplateHelper.map_context(context)
            
            return render(request, self.template_name, context)
            
        except PrivateSessionSlot.DoesNotExist:
            messages.error(request, "Session not found or you don't have permission to cancel it.")
            return redirect('booking:my_sessions')
    
    def post(self, request, slot_id):
        """Process forced late cancellation"""
        # Add force_cancel parameter and redirect to the regular cancellation view
        response = redirect('booking:cancel_booking', slot_id=slot_id)
        response['Location'] += '?force_cancel=true'
        return response


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


class CreateSlotView(LoginRequiredMixin, UserPassesTestMixin, View):
    """View for instructors to create available booking slots"""
    template_name = 'create_slot.html'
    
    def test_func(self):
        """Only users with instructor profiles can create slots"""
        from django.conf import settings
        if hasattr(settings, 'TESTING') and settings.TESTING:
            return True  # Skip permission checks in testing mode
            
        # Check if user has instructor profile in the booking app
        return hasattr(self.request.user, 'booking_instructor_profile')
    
    def get(self, request):
        """Display the slot creation form"""
        # Initialize context with template layout
        context = TemplateLayout.init(self, {
            'active_menu': 'booking',
            'active_submenu': 'instructor_booking',
        })
        
        # Set the layout path using TemplateHelper
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return render(request, self.template_name, context)
    
    def post(self, request):
        """Process slot creation form submission"""
        try:
            # Extract form data
            start_time_str = request.POST.get('start_time')
            duration_minutes = int(request.POST.get('duration', 60))
            
            # Parse the datetime string
            from django.utils import timezone
            import datetime
            
            try:
                # Convert to datetime object and make timezone-aware
                start_time = datetime.datetime.strptime(start_time_str, '%Y-%m-%d %H:%M')
                start_time = timezone.make_aware(start_time)
                end_time = start_time + timezone.timedelta(minutes=duration_minutes)
                
                # Validate the start time (must be in future)
                if start_time <= timezone.now():
                    messages.error(request, "Start time must be in the future.")
                    return redirect('booking:create_slot')
                
            except ValueError:
                messages.error(request, "Invalid date or time format.")
                return redirect('booking:create_slot')
            
            # Get or create instructor profile
            try:
                instructor = Instructor.objects.get(user=request.user)
            except Instructor.DoesNotExist:
                instructor = Instructor.objects.create(
                    user=request.user,
                    bio="",
                    teaching_languages="en",  # Default language
                    hourly_rate=25.00,
                    is_available=True
                )
            
            # Create the slot
            slot = PrivateSessionSlot.objects.create(
                instructor=instructor,
                start_time=start_time,
                end_time=end_time,
                duration_minutes=duration_minutes,
                language='en',  # Default to English
                level='B1',     # Default to Intermediate
                status='available'
            )
            
            # Try syncing with content app if available
            try:
                from apps.content.models import PrivateSession, Instructor as ContentInstructor
                
                # Get or create content instructor
                content_instructor, created = ContentInstructor.objects.get_or_create(
                    user=request.user,
                    defaults={
                        'bio': instructor.bio if hasattr(instructor, 'bio') else '',
                        'hourly_rate': instructor.hourly_rate if hasattr(instructor, 'hourly_rate') else 25.00
                    }
                )
                
                # Create content private session
                PrivateSession.objects.create(
                    instructor=content_instructor,
                    start_time=start_time,
                    end_time=end_time,
                    duration_minutes=duration_minutes,
                    language='en',  # Default to English
                    level='B1',     # Default to Intermediate
                    status='available',
                    is_trial=False
                )
            except (ImportError, AttributeError) as e:
                # Content app not available or models not compatible
                print(f"Warning: Could not sync with content app: {e}")
            
            messages.success(request, "Booking slot created successfully!")
            
        except Exception as e:
            messages.error(request, f"Error creating slot: {str(e)}")
        
        return redirect('booking:dashboard')
