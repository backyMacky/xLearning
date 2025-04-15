from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib.auth.models import User
from .models import BookingSlot, CreditTransaction
from django.utils import timezone
from datetime import datetime, timedelta

@login_required
def booking_dashboard(request):
    """Dashboard for booking system"""
    if request.user.is_teacher:
        # Show teacher's booking slots
        booking_slots = BookingSlot.objects.filter(teacher=request.user).order_by('start_time')
        
        # Group by status
        available_slots = booking_slots.filter(status='available')
        booked_slots = booking_slots.filter(status='booked')
        completed_slots = booking_slots.filter(status='completed')
        cancelled_slots = booking_slots.filter(status='cancelled')
        
        return render(request, 'booking/teacher_dashboard.html', {
            'available_slots': available_slots,
            'booked_slots': booked_slots,
            'completed_slots': completed_slots,
            'cancelled_slots': cancelled_slots
        })
    else:
        # Show student's bookings and available slots from teachers
        my_bookings = BookingSlot.objects.filter(student=request.user).order_by('start_time')
        available_slots = BookingSlot.objects.filter(status='available').order_by('start_time')
        
        # Get student's credit balance
        credit_balance = 0
        if CreditTransaction.objects.filter(student=request.user).exists():
            last_transaction = CreditTransaction.objects.filter(student=request.user).latest('created_at')
            credit_balance = last_transaction.get_balance()
        
        return render(request, 'booking/student_dashboard.html', {
            'my_bookings': my_bookings,
            'available_slots': available_slots,
            'credit_balance': credit_balance
        })

@login_required
def create_booking_slot(request):
    """Create a new booking slot (for teachers)"""
    if not request.user.is_teacher:
        return redirect('booking:dashboard')
    
    if request.method == 'POST':
        start_time_str = request.POST.get('start_time')
        duration = int(request.POST.get('duration', 60))
        
        # Parse start time
        start_time = datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M')
        
        # Create the booking slot
        BookingSlot.objects.create(
            teacher=request.user,
            start_time=start_time,
            duration=duration,
            status='available'
        )
        
        return redirect('booking:dashboard')
    
    # GET request
    return render(request, 'booking/create_slot.html')

@login_required
def book_slot(request, slot_id):
    """Book an available slot (for students)"""
    slot = get_object_or_404(BookingSlot, id=slot_id, status='available')
    
    if not request.user.is_student:
        return redirect('booking:dashboard')
    
    # Check if student has enough credits (assuming 1 credit per session)
    credit_balance = 0
    if CreditTransaction.objects.filter(student=request.user).exists():
        last_transaction = CreditTransaction.objects.filter(student=request.user).latest('created_at')
        credit_balance = last_transaction.get_balance()
    
    if credit_balance < 1:
        return render(request, 'booking/insufficient_credits.html')
    
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
    
    return redirect('booking:dashboard')

@login_required
def cancel_booking(request, slot_id):
    """Cancel a booking"""
    slot = get_object_or_404(BookingSlot, id=slot_id)
    
    # Check permissions
    if request.user.is_teacher and slot.teacher != request.user:
        return redirect('booking:dashboard')
    
    if request.user.is_student and slot.student != request.user:
        return redirect('booking:dashboard')
    
    # Handle cancellation differently based on user type
    if request.user.is_teacher:
        # Teacher cancelling their own slot
        if slot.status == 'available':
            # Just delete it if no student has booked yet
            slot.delete()
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
            else:
                # Too late to cancel with refund
                return render(request, 'booking/late_cancellation.html')
    
    return redirect('booking:dashboard')

@login_required
def purchase_credits(request):
    """Purchase credits (for students)"""
    if not request.user.is_student:
        return redirect('booking:dashboard')
    
    if request.method == 'POST':
        amount = int(request.POST.get('amount', 0))
        
        # In a real app, this would integrate with a payment gateway
        # For now, just add the credits directly
        
        CreditTransaction.objects.create(
            student=request.user,
            amount=amount,
            description=f"Purchase of {amount} credits",
            transaction_type='purchase'
        )
        
        return redirect('booking:dashboard')
    
    # GET request
    return render(request, 'booking/purchase_credits.html')

@login_required
def transaction_history(request):
    """View credit transaction history (for students)"""
    if not request.user.is_student:
        return redirect('booking:dashboard')
    
    transactions = CreditTransaction.objects.filter(student=request.user).order_by('-created_at')
    
    # Calculate current balance
    balance = 0
    if transactions.exists():
        latest_transaction = transactions.first()
        balance = latest_transaction.get_balance()
    
    return render(request, 'booking/transaction_history.html', {
        'transactions': transactions,
        'balance': balance
    })