
import csv
import os
import logging
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from django.conf import settings
from dateutil.relativedelta import relativedelta

logger = logging.getLogger(__name__)

CSV_FILE_PATH = os.path.join(settings.BASE_DIR, 'data', 'transactions.csv')

def calculate_credit_score(aadhar_id: str) -> int:
    """
        makes a user's credit score (b/w 300 to 900) based on their transactions, else returns 300 if it can't be calculated.
    """
    total_credit = Decimal('0.00')
    total_debit = Decimal('0.00')

    try:
        with open(CSV_FILE_PATH, mode='r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if row.get('AADHARID') == aadhar_id:
                    try:
                        amount = Decimal(row.get('Amount', '0'))
                        transaction_type = row.get('Transaction_type', '').upper()

                        if transaction_type == 'CREDIT':
                            total_credit += amount
                        elif transaction_type == 'DEBIT':
                            total_debit += amount
                    except (InvalidOperation, ValueError, TypeError) as e:
                        continue
    except Exception as e:
        logger.error(f"Error in reading CSV for Aadhar {aadhar_id}: {e}", exc_info=True)
        return 300

    account_balance = total_credit - total_debit #total balance

    lower_bound_balance = Decimal('100000')
    upper_bound_balance = Decimal('1000000')
    balance_step = Decimal('15000')
    score_step = 10
    min_score = 300
    max_score = 900

    if account_balance >= upper_bound_balance:
        score = max_score
    elif account_balance <= lower_bound_balance:
        score = min_score
    else:
        steps = int((account_balance - lower_bound_balance) // balance_step)
        score = min_score + (steps * score_step)
        score = min(score, max_score)

    score = max(min_score, min(score, max_score))

    return int(score)


class EMICalculationError(ValueError):
    pass

def calculate_emi_schedule(loan_amount: Decimal, annual_interest_rate: Decimal,
                           term_months: int, annual_income: Decimal,
                           disbursement_date) -> list:
    """
        this function calculates the EMI schedule based on loan details and checks constraints
        and returns a list of EMI payments or raises an error.
    """
    if term_months <= 0:
        raise EMICalculationError("Term period must be greater than 0 months.")
    if loan_amount <= 0:
        raise EMICalculationError("Loan amount should be positive.")

    monthly_rate = annual_interest_rate / Decimal('1200')
    if monthly_rate > 0:
        first_month_interest = (loan_amount * monthly_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        if first_month_interest <= Decimal('50.00'):
            raise EMICalculationError(f"interest calculated for first month (Rs. {first_month_interest:.2f}) must be greater than 50/-.")
    elif loan_amount > 0 :
         raise EMICalculationError("interest calculated for first month should be greater than Rs. 50.")

    if monthly_rate > 0:
        one_plus_r_pow_n = (1 + monthly_rate) ** term_months
        emi_amount = (loan_amount * monthly_rate * one_plus_r_pow_n) / (one_plus_r_pow_n - 1)
        emi_amount = emi_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    else:
        emi_amount = (loan_amount / Decimal(term_months)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    monthly_income = annual_income / Decimal('12')
    max_allowed_emi = (monthly_income * Decimal('0.20')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    if emi_amount > max_allowed_emi:
        raise EMICalculationError(f"calculated EMI (Rs. {emi_amount:.2f}) crosses 20% of monthly income (Max Allowed: Rs. {max_allowed_emi:.2f}).")

    schedule = []
    current_balance = loan_amount
    first_due_date = disbursement_date + relativedelta(months=1)

    for i in range(term_months):
        interest_component = (current_balance * monthly_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        if i == term_months - 1:
            principal_component = current_balance
            actual_emi_for_month = principal_component + interest_component
        else:
            principal_component = emi_amount - interest_component
            actual_emi_for_month = emi_amount

        if principal_component > current_balance:
            principal_component = current_balance
            if i != term_months -1:
                 actual_emi_for_month = principal_component + interest_component

        current_balance -= principal_component
        due_date = first_due_date + relativedelta(months=i)

        schedule.append({
            'due_date': due_date,
            'amount_due': actual_emi_for_month.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            'principal_component': principal_component.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            'interest_component': interest_component.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        })

        if current_balance < Decimal('0.00') and i < term_months - 1:
             current_balance = Decimal('0.00')

    if abs(current_balance) > Decimal('0.01'):
        pass 

    return schedule