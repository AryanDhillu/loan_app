# Backend Intern Assessment

## Introduction

A Django-based finance backend where users can register, apply for loans, manage bills, make payments, and view account statements. Created for the SDE-Intern assessment.

## Features

* User Registration w/ Async Credit Score
* Loan Application
* Atomic Payment Processing
* Billing Generation (via Management Command)
* Statement API

## Workflow Overview

1.  User registers (`/api/register-user/`), Credit Score via Celery.
2.  Eligible user applies for loan (`/api/apply-loan/`).
3.  Daily command (`manage.py run_billing`) generates `Bill` records (requires external scheduling).
4.  User makes payments (`/api/make-payment/`), applied atomically to bills/principal.
5.  User retrieves statement (`/api/get-statement/`).

## Installation Guide

**Prerequisites:** Python, Git, Redis Server running on port 6379.

1.  **Clone:** `git clone <your-repo-url>` & `cd <repo-name>`
2.  **Venv:** `python -m venv venv` & activate (`source venv/bin/activate` or `.\venv\Scripts\activate`)
3.  **Install:** `pip install -r requirements.txt`
4.  **Data File:** Create `data/` folder, add `transactions.csv` with sample data (`AADHARID,Date,Amount,Transaction_type` columns).
5.  **Migrate:** `python manage.py migrate`
6.  **Run Worker:** (New Terminal + Venv) `celery -A bright_project worker -P gevent --loglevel=info`
7.  **Run Server:** (New Terminal + Venv) `python manage.py runserver`
8.  **Access:** API at `http://127.0.0.1:8000/api/`

## APIs and Technical Details

### `/api/register-user/` (POST)
* **Purpose:** Register user, trigger score calculation.
* **Request:** `{ "aadhar_id", "name", "email_id", "annual_income" }`
* **Response:** `{ "Error": null, "unique_user_id": "..." }`

### `/api/apply-loan/` (POST)
* **Purpose:** Apply for a loan.
* **Request:** `{ "unique_user_id", "loan_amount", "interest_rate", "term_period", "disbursement_date" }`
* **Response:** `{ "Error": null, "Loan_id": "...", "Due_dates": [...] }`
* **Note:** Checks eligibility (Score>=450, Income>=150k, Amt<=5k, Rate>=12%, EMI rules).

### `/api/make-payment/` (POST)
* **Purpose:** Record a payment against a loan.
* **Request:** `{ "loan_id": "<Loan-UUID>", "amount": "..." }`
* **Response:** `{ "Error": null }`

### `/api/get-statement/<uuid:loan_id>/` (GET)
* **Purpose:** Retrieve loan history & future estimated dues.
* **Response:** `{ "Error": null, "Past_transactions": [...], "Upcoming_transactions": [...] }`

### `python manage.py run_billing` (Command)
* **Purpose:** Generate monthly bills (Requires external daily scheduling).
* **Note:** Creates `Bill` for active loans due today (30-day cycle). Min Due = 3% Principal + 30 days Interest.

## Sample Output Screenshots

You can view screenshots demonstrating sample API request/response cycles and workflow results here:

* [Sample API Output Screenshots](https://drive.google.com/file/d/1lVcTvM4DqdaoSzQ3-4xhRnq8FY0L_EpL/view?usp=sharing)

---

