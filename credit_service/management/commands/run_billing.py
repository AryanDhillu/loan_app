
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from credit_service.models import Loan, Bill 
from decimal import Decimal, ROUND_HALF_UP
from dateutil.relativedelta import relativedelta
import logging

logger = logging.getLogger(__name__)


TWOPLACES = Decimal('0.01')

class Command(BaseCommand):
    help = 'Runs the daily billing process for active loans.'

    def handle(self, *args, **options):
        today = timezone.now().date()
        self.stdout.write(f"Starting billing run for: {today.strftime('%Y-%m-%d')}")
        logger.info(f"Starting billing run for {today}...")

        billed_count = 0
        skipped_count = 0

        # active and still has a balance
        active_loans = Loan.objects.filter(
            status=Loan.LOAN_STATUS_CHOICES[1][0], 
            principal_balance__gt=Decimal('0.00')
        )

        self.stdout.write(f"Found {active_loans.count()} active loans with balance > 0.")

        for loan in active_loans:
            try:
                last_bill = loan.bills.order_by('-billing_date').first() # expected billing date

                if last_bill:
                    next_billing_date = last_bill.billing_date + relativedelta(days=30)  # next bill
                else:
                    next_billing_date = loan.disbursement_date + relativedelta(days=30)

                # today's bill
                if today == next_billing_date:
                    logger.info(f"Billing due for Loan ID: {loan.loan_id} (User: {loan.user_id})")

                    
                    with transaction.atomic():
                        loan_for_update = Loan.objects.select_for_update().get(id=loan.id)

                        current_principal = loan_for_update.principal_balance
                        if current_principal <= Decimal('0.00'):
                            logger.warning(f"Skipping Loan ID {loan.loan_id} as balance became zero before billing.")
                            skipped_count += 1
                            continue  #  balance == 0

                        daily_rate = loan_for_update.interest_rate / Decimal('36500')
                        days_in_cycle = 30 

                        # 30-day cycle
                        interest_for_cycle = (current_principal * daily_rate * days_in_cycle).quantize(TWOPLACES, rounding=ROUND_HALF_UP)

                        #principal component 
                        principal_component_raw = current_principal * Decimal('0.03')

                        if principal_component_raw >= current_principal:
                            principal_component = current_principal
                        else:
                            principal_component = principal_component_raw.quantize(TWOPLACES, rounding=ROUND_HALF_UP)

                        min_due = (principal_component + interest_for_cycle).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
                        due_date = today + relativedelta(days=15) 

                        #bill record 
                        new_bill = Bill.objects.create(
                            loan=loan_for_update,
                            billing_date=today,
                            due_date=due_date,
                            principal_component=principal_component,
                            interest_component=interest_for_cycle,
                            min_due_amount=min_due,
                            status=Bill.BILL_STATUS_CHOICES[0][0] #'pending'
                        )
                        billed_count += 1
                        logger.info(f"Created Bill ID: {new_bill.id} for Loan ID: {loan.loan_id}. Min Due: {min_due}, Due Date: {due_date}")
                        self.stdout.write(self.style.SUCCESS(f"Successfully billed Loan ID: {loan.loan_id}"))

            except Exception as e:
                logger.error(f"Error processing billing for Loan ID {loan.loan_id}: {e}", exc_info=True)
                self.stdout.write(self.style.ERROR(f"Error billing Loan ID: {loan.loan_id} - Check logs."))

        self.stdout.write(f"Billing run finished. Billed: {billed_count}, Skipped/Error: {skipped_count + (active_loans.count() - billed_count - skipped_count)}")
        logger.info(f"Billing run finished. Billed: {billed_count}")