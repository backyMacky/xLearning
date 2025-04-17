from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView
from django.views.generic.edit import FormView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.models import User
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.contrib import messages
from datetime import datetime, timedelta
from django.db.models import Sum
from web_project import TemplateLayout

from .models import BookingSlot, CreditTransaction

class BookingDashboardView(LoginRequiredMixin, TemplateView):
    """Dashboard for booking system"""
    template_name = 'dashboard.html'
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        now = timezone.now()
        user = self.request.user
        
        # Set active menu attributes
        context['active_menu'] = 'booking'
        context['active_submenu'] = 'booking-slots'
        
        if user.is_teacher:
            # Show teacher's booking slots
            booking_slots = BookingSlot.objects.filter(teacher=user).order_by('start_time')
            
            # Group by status
            available_slots = booking_slots.filter(status='available')
            booked_slots = booking_slots.filter(status='booked')
            completed_slots = booking_slots.filter(status='completed')
            cancelled_slots = booking_slots.filter(status='cancelled')
            
            context.update({
                'available_slots': available_slots,
                'booked_slots': booked_slots,
                'completed_slots': completed_slots,
                'cancelled_slots': cancelled_slots,
                'is_teacher': True,
                'total_slots': booking_slots.count(),
                'total_booked': booked_slots.count(),
                'total_completed': completed_slots.count()
            })
        else:
            # Show student's bookings and available slots from teachers
            my_bookings = BookingSlot.objects.filter(student=user).order_by('start_time')
            available_slots = BookingSlot.objects.filter(status='available', start_time__gt=now).order_by('start_time')
            
            # Get student's credit balance
            credit_balance = 0
            if CreditTransaction.objects.filter(student=user).exists():
                transactions = CreditTransaction.objects.filter(student=user)
                
                # Sum up all credits (purchases, refunds, bonuses)
                credits = transactions.filter(
                    transaction_type__in=['purchase', 'refund', 'bonus']
                ).aggregate(total=Sum('amount'))['total'] or 0
                
                # Sum up all debits (deductions)
                debits = transactions.filter(
                    transaction_type='deduction'
                ).aggregate(total=Sum('amount'))['total'] or 0
                
                # Calculate balance
                credit_balance = credits - debits
            
            context.update({
                'my_bookings': my_bookings,
                'available_slots': available_slots,
                'credit_balance': credit_balance,
                'is_teacher': False,
                'upcoming_sessions': my_bookings.filter(status='booked', start_time__gt=now).count(),
                'completed_sessions': my_bookings.filter(status='completed').count()
            })
        
        return context


class CreateBookingSlotView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Create a new booking slot (for teachers)"""
    model = BookingSlot
    template_name = 'create_slot.html'
    fields = ['start_time', 'duration']
    success_url = reverse_lazy('booking:dashboard')
    
    def test_func(self):
        return self.request.user.is_teacher or self.request.user.is_superuser or self.request.user.is_staff
    
    def form_valid(self, form):
        form.instance.teacher = self.request.user
        form.instance.status = 'available'
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        # Set active menu attributes
        context['active_menu'] = 'booking'
        context['active_submenu'] = 'booking-create'
        context['title'] = 'Create Booking Slot'
        
        return context


class BookSlotView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Book an available slot (for students)"""
    model = BookingSlot
    template_name = 'book_slot.html'
    fields = []  # No fields needed for booking
    pk_url_kwarg = 'slot_id'
    
    def test_func(self):
        return self.request.user.is_student
    
    def get_success_url(self):
        return reverse('booking:dashboard')
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        # Get student's credit balance
        credit_balance = 0
        if CreditTransaction.objects.filter(student=self.request.user).exists():
            transactions = CreditTransaction.objects.filter(student=self.request.user)
            
            # Sum up all credits (purchases, refunds, bonuses)
            credits = transactions.filter(
                transaction_type__in=['purchase', 'refund', 'bonus']
            ).aggregate(total=Sum('amount'))['total'] or 0
            
            # Sum up all debits (deductions)
            debits = transactions.filter(
                transaction_type='deduction'
            ).aggregate(total=Sum('amount'))['total'] or 0
            
            # Calculate balance
            credit_balance = credits - debits
        
        context.update({
            'active_menu': 'booking',
            'active_submenu': 'booking-slots',
            'title': 'Book Session',
            'credit_balance': credit_balance,
            'slot': self.object
        })
        
        return context
    
    def post(self, request, *args, **kwargs):
        slot = self.get_object()
        
        # Check if student has enough credits (assuming 1 credit per session)
        credit_balance = 0
        if CreditTransaction.objects.filter(student=request.user).exists():
            transactions = CreditTransaction.objects.filter(student=request.user)
            
            # Sum up all credits (purchases, refunds, bonuses)
            credits = transactions.filter(
                transaction_type__in=['purchase', 'refund', 'bonus']
            ).aggregate(total=Sum('amount'))['total'] or 0
            
            # Sum up all debits (deductions)
            debits = transactions.filter(
                transaction_type='deduction'
            ).aggregate(total=Sum('amount'))['total'] or 0
            
            # Calculate balance
            credit_balance = credits - debits
        
        if credit_balance < 1:
            messages.error(request, "You don't have enough credits to book this session.")
            return redirect('booking:dashboard')
        
        # Book the slot
        slot.student = request.user
        slot.confirm()
        
        # Deduct credits
        CreditTransaction.objects.create(
            student=request.user,
            amount=1,
            description=f"Booking session with {slot.teacher.username} on {slot.start_time}",
            transaction_type='deduction'
        )
        
        messages.success(request, "Session booked successfully!")
        return redirect('booking:dashboard')


class CancelBookingView(LoginRequiredMixin, UpdateView):
    """Cancel a booking"""
    model = BookingSlot
    template_name = 'cancel_booking.html'
    fields = []  # No fields needed for cancellation
    pk_url_kwarg = 'slot_id'
    
    def get_success_url(self):
        return reverse('booking:dashboard')
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        # Check permissions
        slot = self.object
        user = self.request.user
        
        if user.is_teacher and slot.teacher != user:
            return redirect('booking:dashboard')
        
        if user.is_student and slot.student != user:
            return redirect('booking:dashboard')
        
        context.update({
            'active_menu': 'booking',
            'active_submenu': 'booking-slots',
            'title': 'Cancel Booking',
            'slot': slot
        })
        
        return context
    
    def post(self, request, *args, **kwargs):
        slot = self.get_object()
        
        # Check permissions
        if request.user.is_teacher and slot.teacher != request.user:
            messages.error(request, "You don't have permission to cancel this booking.")
            return redirect('booking:dashboard')
        
        if request.user.is_student and slot.student != request.user:
            messages.error(request, "You don't have permission to cancel this booking.")
            return redirect('booking:dashboard')
        
        # Handle cancellation differently based on user type
        if request.user.is_teacher:
            # Teacher cancelling their own slot
            if slot.status == 'available':
                # Just delete it if no student has booked yet
                slot.delete()
                messages.success(request, "Slot deleted successfully.")
            else:
                # Cancel and refund student if already booked
                student = slot.student
                slot.cancel()
                
                # Refund credits to student
                if student:
                    CreditTransaction.objects.create(
                        student=student,
                        amount=1,
                        description=f"Refund for cancelled session with {slot.teacher.username}",
                        transaction_type='refund'
                    )
                messages.success(request, "Booking cancelled and student refunded.")
        else:
            # Student cancelling their booking
            if slot.status == 'booked':
                # Check if cancellation is allowed (e.g., not too close to start time)
                if slot.start_time - timezone.now() > timedelta(hours=24):
                    # Cancel and refund
                    slot.cancel()
                    
                    CreditTransaction.objects.create(
                        student=request.user,
                        amount=1,
                        description=f"Refund for cancelled session with {slot.teacher.username}",
                        transaction_type='refund'
                    )
                    messages.success(request, "Booking cancelled and credits refunded.")
                else:
                    # Too late to cancel with refund
                    messages.error(request, "Cannot cancel booking less than 24 hours before the session.")
                    return redirect('booking:dashboard')
        
        return redirect('booking:dashboard')


class PurchaseCreditsView(LoginRequiredMixin, UserPassesTestMixin, FormView):
    """Purchase credits (for students)"""
    template_name = 'purchase_credits.html'
    success_url = reverse_lazy('booking:dashboard')
    
    def test_func(self):
        # Allow both students and superusers/staff
        return self.request.user.is_student or self.request.user.is_superuser or self.request.user.is_staff
    
    def get_form_class(self):
        # Create a simple form with just an amount field
        from django import forms
        
        class PurchaseCreditsForm(forms.Form):
            amount = forms.IntegerField(widget=forms.HiddenInput())
            
        return PurchaseCreditsForm
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        context.update({
            'active_menu': 'booking',
            'active_submenu': 'booking-credits',
            'title': 'Purchase Credits',
            'credit_options': [5, 10, 20, 50]  # Credit package options
        })
        
        return context
    
    def form_valid(self, form):
        amount = int(self.request.POST.get('amount', 0))
        
        # In a real app, this would integrate with a payment gateway
        # For now, just add the credits directly
        
        CreditTransaction.objects.create(
            student=self.request.user,
            amount=amount,
            description=f"Purchase of {amount} credits",
            transaction_type='purchase'
        )
        
        messages.success(self.request, f"Successfully purchased {amount} credits!")
        return super().form_valid(form)


class TransactionHistoryView(LoginRequiredMixin, TemplateView):
    """View credit transaction history (for students)"""
    template_name = 'transaction_history.html'
    
    def dispatch(self, request, *args, **kwargs):
        # Check if user is a student or admin
        if not (hasattr(request.user, 'is_student') and request.user.is_student) and not (request.user.is_superuser or request.user.is_staff):
            messages.error(request, "You do not have permission to view this page.")
            return redirect('booking:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        # Get transactions for this user
        transactions = CreditTransaction.objects.filter(
            student=self.request.user
        ).order_by('-created_at')
        
        # Calculate current balance
        balance = 0
        if transactions.exists():
            # Sum up all credits (purchases, refunds, bonuses)
            credits = transactions.filter(
                transaction_type__in=['purchase', 'refund', 'bonus']
            ).aggregate(total=Sum('amount'))['total'] or 0
            
            # Sum up all debits (deductions)
            debits = transactions.filter(
                transaction_type='deduction'
            ).aggregate(total=Sum('amount'))['total'] or 0
            
            # Calculate balance
            balance = credits - debits
        
        context.update({
            'active_menu': 'booking',
            'active_submenu': 'booking-transactions',
            'title': 'Transaction History',
            'balance': balance,
            'transactions': transactions
        })
        
        return context

class InsufficientCreditsView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """View displayed when a student has insufficient credits"""
    template_name = 'insufficient_credits.html'
    
    def test_func(self):
        return self.request.user.is_student
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        context.update({
            'active_menu': 'booking',
            'active_submenu': 'booking-slots',
            'title': 'Insufficient Credits'
        })
        
        return context


class LateCancellationView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """View displayed when a student tries to cancel a booking less than 24 hours before it starts"""
    model = BookingSlot
    template_name = 'late_cancellation.html'
    context_object_name = 'slot'
    pk_url_kwarg = 'slot_id'
    
    def test_func(self):
        return self.request.user.is_student
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        context.update({
            'active_menu': 'booking',
            'active_submenu': 'booking-slots',
            'title': 'Late Cancellation'
        })
        
        return context
