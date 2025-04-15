from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from apps.meetings.models import Meeting


class BookingSlot(models.Model):
    """Model for managing bookable time slots"""
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='offered_booking_slots')
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='booked_slots', null=True, blank=True)
    start_time = models.DateTimeField()
    duration = models.IntegerField(help_text="Duration in minutes")
    status = models.CharField(max_length=20, choices=[
        ('available', 'Available'),
        ('booked', 'Booked'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], default='available')
    meeting = models.ForeignKey(Meeting, on_delete=models.SET_NULL, null=True, blank=True, related_name='booking_slot')
    
    def __str__(self):
        status_text = f"[{self.status.upper()}]"
        if self.student:
            return f"{status_text} {self.teacher.username} with {self.student.username} - {self.start_time.strftime('%Y-%m-%d %H:%M')}"
        return f"{status_text} {self.teacher.username} - {self.start_time.strftime('%Y-%m-%d %H:%M')}"
    
    def confirm(self):
        """Confirm booking after student books a slot"""
        if self.status == 'available' and self.student is not None:
            self.status = 'booked'
            self.save()
            
            # Create a meeting for this booking
            meeting = Meeting.objects.create(
                title=f"Session: {self.teacher.username} and {self.student.username}",
                teacher=self.teacher,
                start_time=self.start_time,
                duration=self.duration,
                meeting_link=f"https://meet.google.com/{self.teacher.username}-{self.student.username}-{timezone.now().strftime('%Y%m%d%H%M')}"
            )
            meeting.students.add(self.student)
            
            # Link meeting to booking
            self.meeting = meeting
            self.save()
            
            return True
        return False
    
    def cancel(self):
        """Cancel a booking"""
        if self.status == 'booked':
            self.status = 'cancelled'
            if self.meeting:
                # You might want to handle the meeting differently, like marking it cancelled
                # instead of deleting it
                self.meeting.delete()
                self.meeting = None
            self.student = None
            self.save()
            return True
        return False


class CreditTransaction(models.Model):
    """Model for tracking credit transactions"""
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='credit_transactions')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField()
    transaction_type = models.CharField(max_length=20, choices=[
        ('purchase', 'Purchase'),
        ('refund', 'Refund'),
        ('deduction', 'Deduction'),
        ('bonus', 'Bonus'),
    ])
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.student.username} - {self.transaction_type} - {self.amount}"
    
    def get_balance(self):
        """Calculate the current credit balance for the student"""
        transactions = CreditTransaction.objects.filter(student=self.student)
        
        # Sum up all credits (purchases, refunds, bonuses)
        credits = transactions.filter(
            transaction_type__in=['purchase', 'refund', 'bonus']
        ).aggregate(total=models.Sum('amount'))['total'] or 0
        
        # Sum up all debits (deductions)
        debits = transactions.filter(
            transaction_type='deduction'
        ).aggregate(total=models.Sum('amount'))['total'] or 0
        
        # Calculate balance
        balance = credits - debits
        return balance