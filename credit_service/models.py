
from django.db import models
import uuid
from decimal import Decimal

#user model
class User(models.Model):
    unique_user_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    aadhar_id = models.CharField(max_length=12, unique=True, db_index=True)
    name = models.CharField(max_length=100)
    email_id = models.EmailField(unique=True)
    annual_income = models.DecimalField(max_digits=15, decimal_places=2)
    credit_score = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.aadhar_id})"

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ['-created_at']


#loan model
class Loan(models.Model):
    LOAN_STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Active', 'Active'),
        ('Closed', 'Closed'),
        ('Rejected', 'Rejected'),
    ]
    LOAN_TYPE_CHOICES = [
        ('Credit Card', 'Credit Card'),
    ]

    loan_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='loans')
    loan_type = models.CharField(max_length=50, choices=LOAN_TYPE_CHOICES, default='Credit Card')
    loan_amount = models.DecimalField(max_digits=10, decimal_places=2)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2)
    term_period = models.IntegerField()
    disbursement_date = models.DateField()
    status = models.CharField(max_length=20, choices=LOAN_STATUS_CHOICES, default='Pending')
    principal_balance = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Loan {self.loan_id} for {self.user.name}"

    class Meta:
        verbose_name = "Loan"
        verbose_name_plural = "Loans"
        ordering = ['-created_at']



#bill model
class Bill(models.Model):
    BILL_STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Paid', 'Paid'),
        ('Partially Paid', 'Partially Paid'),
        ('Overdue', 'Overdue'),
    ]

    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='bills')
    billing_date = models.DateField()
    due_date = models.DateField()
    principal_component = models.DecimalField(max_digits=10, decimal_places=2)
    interest_component = models.DecimalField(max_digits=10, decimal_places=2)
    min_due_amount = models.DecimalField(max_digits=10, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    status = models.CharField(max_length=20, choices=BILL_STATUS_CHOICES, default='Pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Bill for Loan {self.loan.loan_id} due {self.due_date}"

    class Meta:
        verbose_name = "Bill"
        verbose_name_plural = "Bills"
        ordering = ['billing_date']



#payment model
class Payment(models.Model):
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payment of {self.amount} for Loan {self.loan.loan_id} on {self.payment_date}"

    class Meta:
        verbose_name = "Payment"
        verbose_name_plural = "Payments"
        ordering = ['-payment_date']