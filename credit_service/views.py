
import logging # Keep logging import for logger.error
from decimal import Decimal, ROUND_HALF_UP

# Django & DRF Imports
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django.http import Http404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from dateutil.relativedelta import relativedelta
from .models import User, Loan, Bill, Payment

from .serializers import (
    UserRegistrationSerializer, UserResponseSerializer,
    LoanApplicationSerializer, LoanResponseSerializer,
    MakePaymentSerializer, PastTransactionSerializer, UpcomingTransactionSerializer
)

from .tasks import update_user_credit_score
from .utils import calculate_emi_schedule, EMICalculationError


logger = logging.getLogger(__name__)

# Constants for GetStatementView
TWOPLACES = Decimal('0.01')
DAYS_IN_YEAR = Decimal('365')
PRINCIPAL_PERCENTAGE = Decimal('0.03')
BILLING_CYCLE_DAYS = 30


# User registration
class RegisterUserView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = UserRegistrationSerializer(data=request.data)

        if serializer.is_valid():
            try:
                user = User.objects.create(
                    aadhar_id=serializer.validated_data['aadhar_id'],
                    name=serializer.validated_data['name'],
                    email_id=serializer.validated_data['email_id'],
                    annual_income=serializer.validated_data['annual_income']
                )

                task_result = update_user_credit_score.delay(user.id)

                response_serializer = UserResponseSerializer(user)
                return Response({
                    "Error": None,
                    **response_serializer.data
                }, status=status.HTTP_200_OK)

            except Exception as e:
                logger.error(f"Error at user registration: {e}", exc_info=True)
                return Response({"Error": "An internal error occurred"}, status=status.HTTP_400_BAD_REQUEST)
        else:
            error_string = "; ".join([f"{field}: {' '.join(errs)}" for field, errs in serializer.errors.items()])
            return Response({"Error": f"Validation Failed: {error_string}"}, status=status.HTTP_400_BAD_REQUEST)



# Loan application
class ApplyLoanView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = LoanApplicationSerializer(data=request.data)
        if not serializer.is_valid():
            error_string = "; ".join([f"{field}: {' '.join(errs)}" for field, errs in serializer.errors.items()])
            return Response({"Error": f"Validation Failed: {error_string}"}, status=status.HTTP_400_BAD_REQUEST)

        validated_data = serializer.validated_data

        try:
            user = User.objects.get(unique_user_id=validated_data['unique_user_id'])
        except User.DoesNotExist:
            return Response({"Error": "User not found."}, status=status.HTTP_400_BAD_REQUEST)


        if user.credit_score is None:
            return Response({"Error": "User credit score not found."}, status=status.HTTP_400_BAD_REQUEST)
        if user.credit_score < 450:
            return Response({"Error": f"Credit score ({user.credit_score}) is below required minimum (450)."}, status=status.HTTP_400_BAD_REQUEST)
        if user.annual_income < Decimal('150000.00'):
            return Response({"Error": f"Annual income ({user.annual_income}) is below required minimum (150000)."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            emi_schedule_details = calculate_emi_schedule(
                loan_amount=validated_data['loan_amount'],
                annual_interest_rate=validated_data['interest_rate'],
                term_months=validated_data['term_period'],
                annual_income=user.annual_income,
                disbursement_date=validated_data['disbursement_date']
            )

        except EMICalculationError as e:
            return Response({"Error": f"Loan rejected: {e}"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"error at EMI calculation for user {user.id}: {e}", exc_info=True)
            return Response({"Error": "Failed to calculate EMI schedule beacuse of internal error."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                loan = Loan.objects.create(
                    user=user,
                    loan_type='Credit Card',
                    loan_amount=validated_data['loan_amount'],
                    interest_rate=validated_data['interest_rate'],
                    term_period=validated_data['term_period'],
                    disbursement_date=validated_data['disbursement_date'],
                    principal_balance=validated_data['loan_amount'],
                    status='Active'
                )

        except Exception as e:
            logger.error(f"failed to save loan record for user {user.id}: {e}", exc_info=True)
            return Response({"Error": "failed to create loan record due to an internal error."}, status=status.HTTP_400_BAD_REQUEST)

        due_dates_response = [
            {"Date": item['due_date'], "Amount_due": item['amount_due']}
            for item in emi_schedule_details
        ]

        response_data = {
            "Loan_id": loan.loan_id,
            "Due_dates": due_dates_response
        }
        response_serializer = LoanResponseSerializer(data=response_data)
        if response_serializer.is_valid():
             return Response({
                "Error": None,
                **response_serializer.data
            }, status=status.HTTP_200_OK)
        else:
             logger.error(f"LoanResponseSerializer failed validation for loan {loan.loan_id}: {response_serializer.errors}")
             return Response({"Error": "failed to format successful response."}, status=status.HTTP_400_BAD_REQUEST)



# make Payment
class MakePaymentView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = MakePaymentSerializer(data=request.data)
        if not serializer.is_valid():
            error_string = "; ".join([f"{field}: {' '.join(errs)}" for field, errs in serializer.errors.items()])
            return Response({"Error": f"Validation Failed: {error_string}"}, status=status.HTTP_400_BAD_REQUEST)

        validated_data = serializer.validated_data
        loan_id = validated_data['loan_id']
        payment_amount = validated_data['amount']
        payment_timestamp = timezone.now()


        try:
            with transaction.atomic():
                try:
                    loan = Loan.objects.select_for_update().get(loan_id=loan_id)
                except Loan.DoesNotExist:
                    return Response({"Error": "loan not found."}, status=status.HTTP_400_BAD_REQUEST)

                if loan.status != 'Active':
                     return Response({"Error": f"loan is not active (Status: {loan.status})."}, status=status.HTTP_400_BAD_REQUEST)

                outstanding_bills = Bill.objects.select_for_update().filter(
                    loan=loan,
                    status__in=[
                        Bill.BILL_STATUS_CHOICES[0][0],
                        Bill.BILL_STATUS_CHOICES[2][0],
                        Bill.BILL_STATUS_CHOICES[3][0]
                    ]
                ).order_by('due_date', 'id')

                if not outstanding_bills.exists() and loan.principal_balance <= Decimal('0.00'):
                    return Response({"Error": "no outstanding amount or bills found for this loan."}, status=status.HTTP_400_BAD_REQUEST)

                remaining_payment = payment_amount
                principal_reduction_total = Decimal('0.00')

                for bill in outstanding_bills:
                    if remaining_payment <= Decimal('0.00'):
                        break

                    amount_due_on_bill = bill.min_due_amount - bill.amount_paid
                    payment_for_this_bill = min(remaining_payment, amount_due_on_bill)

                    if payment_for_this_bill > Decimal('0.00'):
                        current_numeric_amount_paid = bill.amount_paid
                        if current_numeric_amount_paid + payment_for_this_bill >= bill.min_due_amount:
                             new_status = Bill.BILL_STATUS_CHOICES[1][0] # paid
                        else:
                             new_status = Bill.BILL_STATUS_CHOICES[2][0] # partially paid

                        bill.amount_paid = F('amount_paid') + payment_for_this_bill
                        bill.status = new_status
                        bill.save(update_fields=['amount_paid', 'status', 'updated_at'])
                        remaining_payment -= payment_for_this_bill

                if remaining_payment > Decimal('0.00') and loan.principal_balance > Decimal('0.00'):
                    principal_reduction = min(remaining_payment, loan.principal_balance)
                    loan.principal_balance = F('principal_balance') - principal_reduction
                    principal_reduction_total = principal_reduction
                    loan.save(update_fields=['principal_balance', 'updated_at'])
                    loan.refresh_from_db()

                Payment.objects.create(
                    loan=loan,
                    amount=payment_amount,
                    payment_date=payment_timestamp
                )

                has_outstanding_bills = Bill.objects.filter(
                    loan=loan,
                    status__in=[
                        Bill.BILL_STATUS_CHOICES[0][0],
                        Bill.BILL_STATUS_CHOICES[2][0],
                        Bill.BILL_STATUS_CHOICES[3][0]
                    ]
                ).exists()

                if loan.principal_balance <= Decimal('0.00') and not has_outstanding_bills:
                    loan.status = Loan.LOAN_STATUS_CHOICES[2][0] # Closed
                    loan.save(update_fields=['status', 'updated_at'])

            return Response({"Error": None}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"error processing payment for ID {loan_id}: {e}", exc_info=True)
            return Response({"Error": "payment processing failed due to a internal error."}, status=status.HTTP_400_BAD_REQUEST)



#get statement
class GetStatementView(APIView):
    def get(self, request, loan_id, *args, **kwargs):
        try:
            loan = Loan.objects.filter(loan_id=loan_id).first()

            if not loan:
                return Response({"Error": "loan do not exist."}, status=status.HTTP_404_NOT_FOUND)

            if loan.status == Loan.LOAN_STATUS_CHOICES[2][0]: # Closed
                 return Response({"Error": "loan is closed."}, status=status.HTTP_400_BAD_REQUEST)

            past_transactions_data = []
            past_bills = Bill.objects.filter(loan=loan).order_by('billing_date')

            for bill in past_bills:
                past_transactions_data.append({
                    "Date": bill.billing_date,
                    "Principal": bill.principal_component,
                    "Interest": bill.interest_component,
                    "Amount_paid": bill.amount_paid
                })
            past_serializer = PastTransactionSerializer(past_transactions_data, many=True)

            upcoming_transactions_data = []
            current_principal = loan.principal_balance
            daily_rate = loan.interest_rate / (DAYS_IN_YEAR * 100)

            if past_bills.exists():
                last_known_billing_date = past_bills.last().billing_date
            else:
                last_known_billing_date = loan.disbursement_date

            cycles_billed = past_bills.count()
            cycles_remaining = loan.term_period - cycles_billed
            cycles_to_simulate = max(0, min(cycles_remaining, 24))
            simulated_billing_date = last_known_billing_date

            for i in range(cycles_to_simulate):
                if current_principal <= Decimal('0.00'):
                    break

                next_billing_date = simulated_billing_date + relativedelta(days=BILLING_CYCLE_DAYS)
                interest_for_cycle = (current_principal * daily_rate * BILLING_CYCLE_DAYS).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
                principal_component_raw = current_principal * PRINCIPAL_PERCENTAGE

                if principal_component_raw >= current_principal:
                    principal_component = current_principal
                else:
                    principal_component = principal_component_raw.quantize(TWOPLACES, rounding=ROUND_HALF_UP)

                expected_min_due = (principal_component + interest_for_cycle).quantize(TWOPLACES, rounding=ROUND_HALF_UP)

                upcoming_transactions_data.append({
                    "Date": next_billing_date,
                    "Amount_due": expected_min_due
                })

                current_principal -= principal_component
                simulated_billing_date = next_billing_date

            upcoming_serializer = UpcomingTransactionSerializer(upcoming_transactions_data, many=True)

            response_payload = {
                "Error": None,
                "Past_transactions": past_serializer.data,
                "Upcoming_transactions": upcoming_serializer.data
            }
            return Response(response_payload, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error in generating statement for Loan ID {loan_id}: {e}", exc_info=True)
            return Response({"Error": "failed to generate statement due to internal error."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)