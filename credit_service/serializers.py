
from rest_framework import serializers
from .models import User
from decimal import Decimal
import uuid


#UserRegistrationSerializer
class UserRegistrationSerializer(serializers.Serializer):
    aadhar_id = serializers.CharField(max_length=12, min_length=12) 
    name = serializers.CharField(max_length=100)
    email_id = serializers.EmailField()
    annual_income = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=Decimal('0.00'))

    def validate_aadhar_id(self, value):
        if not value.isdigit(): # AadharID already exists.
            raise serializers.ValidationError("Aadhar ID must contain only digits.")
        if User.objects.filter(aadhar_id=value).exists():
            raise serializers.ValidationError("User with this Aadhar ID already exists.")
        return value

    def validate_email_id(self, value):
        if User.objects.filter(email_id=value).exists():
            raise serializers.ValidationError("User with this Email ID already exists.")
        return value
    

class UserResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['unique_user_id'] 





#LoanApplicationSerializer
class LoanApplicationSerializer(serializers.Serializer):
    unique_user_id = serializers.UUIDField()
    loan_amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0.01'), max_value=Decimal('5000.00'))
    interest_rate = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=Decimal('12.00')) # Min 12%
    term_period = serializers.IntegerField(min_value=1) # minimum 1 month
    disbursement_date = serializers.DateField()


class EMIDetailSerializer(serializers.Serializer):
    Date = serializers.DateField(format="%Y-%m-%d") 
    Amount_due = serializers.DecimalField(max_digits=10, decimal_places=2)


class LoanResponseSerializer(serializers.Serializer):
    Loan_id = serializers.UUIDField()
    Due_dates = EMIDetailSerializer(many=True)


#MakePaymentSerializer
class MakePaymentSerializer(serializers.Serializer):
    loan_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0.01')) 




#PastTransactionSerialzer
class PastTransactionSerializer(serializers.Serializer):
    Date = serializers.DateField(format="%Y-%m-%d") 
    Principal = serializers.DecimalField(max_digits=10, decimal_places=2) 
    Interest = serializers.DecimalField(max_digits=10, decimal_places=2)
    Amount_paid = serializers.DecimalField(max_digits=10, decimal_places=2) 

class UpcomingTransactionSerializer(serializers.Serializer):
    Date = serializers.DateField(format="%Y-%m-%d") 
    Amount_due = serializers.DecimalField(max_digits=10, decimal_places=2)

