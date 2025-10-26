# bryl.py (FINAL, COMPLETE, and FIXED CODE)

from flask import Flask, render_template, request, redirect, session, url_for, flash, get_flashed_messages
from flask_sqlalchemy import SQLAlchemy
import os
from datetime import datetime
from sqlalchemy.orm import joinedload
from models.db import db
from models.user import User, UserModel
# CRITICAL: Ensure all Models are imported here
from models.post import Post, PostModel, LoanModel, PaymentModel
import math  # Import math for monthly payment calculation

bryl = Flask(__name__)
bryl.secret_key = "bryl_secret_key"

# Database setup (SQLite)
bryl.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///loansystem.db"
bryl.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize db *with* the app instance
db.init_app(bryl)

# Initialize the User and Post repositories
# NOTE: User and Post objects are only used for their methods, they don't hold state
user_repo = User(None)
post_repo = Post(None)


# --- Context Processor to make session variables available in all templates ---
@bryl.context_processor
def inject_user_data():
    return dict(
        session=session,
        fullname=session.get('fullname'),
        role=session.get('role')
    )


# ------------------------------------------------------------------
# --- DECORATORS / UTILITIES ---
# ------------------------------------------------------------------

def login_required(f):
    """Decorator to check if a user is logged in."""

    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("You must be logged in to access that page.", "warning")
            return redirect(url_for('home'))
        return f(*args, **kwargs)

    decorated_function.__name__ = f.__name__  # Fix for flask endpoint naming
    return decorated_function


def admin_required(f):
    """Decorator to check if a user is logged in AND is an Admin."""

    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'Admin':
            flash("You do not have permission to access that page.", "danger")
            return redirect(url_for('dashboard'))  # Redirect non-admins to their dashboard
        return f(*args, **kwargs)

    decorated_function.__name__ = f.__name__
    return decorated_function


# ------------------------------------------------------------------
# --- GENERAL ROUTES (Home, Login, Logout, Info) ---
# ------------------------------------------------------------------

@bryl.route("/")
def home():
    if 'email' in session:
        if session.get('role') == 'Admin':
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('dashboard'))
    # Directs to index.html which contains the login form
    return render_template("index.html")


@bryl.route("/login", methods=['POST'])
def login():
    email = request.form.get('email')
    password = request.form.get('password')

    user_data = user_repo.get_user_by_email(email)

    if user_data and user_data.check_password(password):
        if not user_data.is_approved:
            flash("Your account is pending administrator approval. Please wait.", "warning")
            return redirect(url_for('home'))

        # Set session variables
        session['user_id'] = user_data.id
        session['email'] = user_data.email
        session['fullname'] = user_data.fullname
        session['role'] = user_data.role
        session['is_approved'] = user_data.is_approved
        flash(f"Welcome back, {user_data.fullname}!", "success")

        if user_data.role == 'Admin':
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('dashboard'))
    else:
        flash("Invalid email or password.", "danger")
        return redirect(url_for('home'))


@bryl.route("/register", methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        fullname = request.form.get('fullname')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        role = request.form.get('role')

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect(url_for('register'))

        # The 'is_approved' flag is handled by the repository: Admin accounts are auto-approved.
        if user_repo.create_user(fullname, email, password, role):
            if role == 'Admin':
                flash("Admin account created and automatically approved. You can now log in.", "success")
            else:
                flash("Registration successful! Your account is pending administrator approval.", "success")
            return redirect(url_for('home'))
        else:
            flash("Registration failed. An account with that email may already exist.", "danger")
            return redirect(url_for('register'))

    return render_template("register.html")


@bryl.route("/logout")
@login_required
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('home'))


@bryl.route("/about")
def about():
    # Renders the 'about.html' template
    return render_template("about.html")


@bryl.route("/contact")
def contact():
    # Renders the 'contact.html' template
    return render_template("contact.html")


@bryl.route("/forgot_password")
def forgot_password():
    # Renders the 'forgot_password.html' template
    return render_template("forgot_password.html")


# ------------------------------------------------------------------
# --- BORROWER DASHBOARD ROUTES ---
# ------------------------------------------------------------------

@bryl.route("/dashboard")
@login_required
def dashboard():
    if session.get('role') == 'Admin':
        return redirect(url_for('admin_dashboard'))

    user_id = session['user_id']
    is_approved = session.get('is_approved', False)

    # Only fetch data if the user is approved
    user_loans = []
    user_payments = []
    if is_approved:
        # Fetch approved loans
        user_loans = LoanModel.query.filter_by(user_id=user_id, status='Approved').all()

        # Calculate monthly payment for each loan
        # This is a basic example; real-world loan calculations are more complex.
        for loan in user_loans:
            P = loan.amount  # Principal
            r = loan.interest_rate / 100 / 12  # Monthly interest rate
            n = loan.term_months  # Total number of payments

            if r > 0 and n > 0:
                # Formula for fixed-rate loan monthly payment
                loan.monthly_payment = P * (r * (1 + r) ** n) / ((1 + r) ** n - 1)
            else:
                loan.monthly_payment = P / n if n > 0 else P

        # Fetch approved payments
        user_payments = PaymentModel.query.filter_by(user_id=user_id, status='Approved').order_by(
            PaymentModel.payment_date.desc()).all()

    return render_template(
        "dashboard.html",
        is_approved=is_approved,
        user_loans=user_loans,
        user_payments=user_payments,
        role=session.get('role')
    )


@bryl.route("/apply_loan", methods=['GET'])
@login_required
def apply_loan():
    if session.get('role') == 'Admin':
        flash("Admins cannot apply for loans.", "danger")
        return redirect(url_for('admin_dashboard'))

    if not session.get('is_approved', False):
        flash("Your account must be approved before you can apply for a loan.", "warning")
        return redirect(url_for('dashboard'))

    return render_template("apply_loan.html")


@bryl.route('/apply_loan', methods=['GET', 'POST'])
def submit_loan():
    if 'user_id' not in session:
        flash('Please log in to apply for a loan.', 'danger')
        return redirect(url_for('login'))

    if request.method == 'POST':
        try:
            loan_amount = float(request.form.get('loan_amount'))
            # --- CRITICAL FIX: Extract the new fields ---
            interest_rate = float(request.form.get('interest_rate'))
            term_months = int(request.form.get('term_months'))

            user_id = session.get('user_id')

            # --- CRITICAL FIX: Pass the new fields to your repository call ---
            success = post_repo.create_loan(
                user_id=user_id,
                amount=loan_amount,
                interest_rate=interest_rate,
                term_months=term_months
            )

            if success:
                flash('Loan application submitted successfully and is awaiting approval!', 'success')
                return redirect(url_for('dashboard'))
            else:
                # This handles the error reported by your repository's try/except block
                flash('An unexpected database error occurred during loan submission.', 'danger')
                return redirect(url_for('submit_loan'))

        except (ValueError, TypeError) as e:
            # Catches errors if input fields are empty or not the correct number/integer format
            flash('Invalid input. Please ensure Amount, Interest Rate, and Term are valid numbers.', 'danger')
            return redirect(url_for('submit_loan'))

        except Exception as e:
            # General catch-all for unknown errors
            print(f"Loan submission failed: {e}")
            flash('An unexpected error occurred during loan submission. Check server logs.', 'danger')
            return redirect(url_for('submit_loan'))

    return render_template('apply_loan.html')


@bryl.route("/payment", methods=['GET', 'POST'])
@login_required
def payment():
    if session.get('role') == 'Admin':
        flash("Admins cannot make payments.", "danger")
        return redirect(url_for('admin_dashboard'))

    if not session.get('is_approved', False):
        flash("Your account must be approved to make payments.", "warning")
        return redirect(url_for('dashboard'))

    user_id = session['user_id']
    # Fetch all APPROVED loans that still have a balance
    approved_loans = LoanModel.query.filter(
        LoanModel.user_id == user_id,
        LoanModel.status == 'Approved',
        LoanModel.balance > 0
    ).all()

    if request.method == 'POST':
        try:
            loan_id = request.form.get('loan_id')
            amount = float(request.form.get('amount'))
            method = request.form.get('method')

            # Basic validation
            if not loan_id or amount <= 0 or not method:
                flash("Invalid loan ID, amount, or payment method.", "danger")
                return redirect(url_for('payment'))

            loan = LoanModel.query.get(loan_id)
            if not loan or loan.user_id != user_id or loan.status != 'Approved':
                flash("Selected loan is not valid for payment.", "danger")
                return redirect(url_for('payment'))

            # Check if payment amount exceeds the balance (optional but good practice)
            if amount > loan.balance:
                flash(f"Payment amount (₱{amount:,.2f}) cannot exceed the remaining balance (₱{loan.balance:,.2f}).",
                      "danger")
                return redirect(url_for('payment'))

            # Create new payment request
            new_payment = PaymentModel(
                user_id=user_id,
                loan_id=loan_id,
                amount=amount,
                method=method,
                status='Pending',
                payment_date=datetime.utcnow()
            )
            db.session.add(new_payment)
            db.session.commit()

            flash("Payment request submitted successfully! Awaiting administrator approval.", "success")
            return redirect(url_for('dashboard'))

        except ValueError:
            flash("Invalid amount entered for payment.", "danger")
        except Exception as e:
            db.session.rollback()
            flash(f"An unexpected error occurred during payment submission.", "danger")

        return redirect(url_for('payment'))

    return render_template("payment.html", approved_loans=approved_loans)


@bryl.route("/update_profile", methods=['GET', 'POST'])
@login_required
def update_profile():
    user_id = session['user_id']
    user = user_repo.get_user_by_id(user_id)

    if request.method == 'POST':
        fullname = request.form.get('fullname')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        new_password = None
        if password:
            if password != confirm_password:
                flash("New passwords do not match.", "danger")
                return redirect(url_for('update_profile'))
            new_password = password

        if user_repo.update_user(user_id, fullname=fullname, password=new_password):
            session['fullname'] = fullname  # Update session variable
            flash("Profile updated successfully!", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Failed to update profile. Please try again.", "danger")
            return redirect(url_for('update_profile'))

    return render_template("update_profile.html", user=user)


# ------------------------------------------------------------------
# --- ADMIN ROUTES ---
# ------------------------------------------------------------------

@bryl.route("/admin_dashboard")
@admin_required
def admin_dashboard():
    # Fetch overview counts
    user_count = UserModel.query.count()
    loan_count = LoanModel.query.count()
    payment_count = PaymentModel.query.count()

    # Fetch pending requests
    pending_users = UserModel.query.filter_by(is_approved=False).all()

    # Eager load the borrower for pending loans to access 'loan.borrower.fullname'
    pending_loans = LoanModel.query.options(joinedload(LoanModel.borrower)).filter_by(status='Pending').all()

    # Eager load the borrower for pending payments
    pending_payments = PaymentModel.query.options(joinedload(PaymentModel.borrower)).filter_by(status='Pending').all()

    return render_template(
        "admin_dashboard.html",
        user_count=user_count,
        loan_count=loan_count,
        payment_count=payment_count,
        pending_users=pending_users,
        pending_loans=pending_loans,
        pending_payments=pending_payments
    )


# --- Approval Actions ---

@bryl.route("/admin/approve_user/<int:user_id>", methods=['POST'])
@admin_required
def approve_user(user_id):
    if user_repo.update_user(user_id, is_approved=True):
        flash(f"User ID {user_id} approved.", "success")
    else:
        flash(f"Failed to approve user ID {user_id}.", "danger")
    return redirect(url_for('admin_dashboard'))


@bryl.route("/admin/deny_user/<int:user_id>", methods=['POST'])
@admin_required
def deny_user(user_id):
    if user_repo.delete_user(user_id):
        flash(f"User ID {user_id} denied and deleted.", "warning")
    else:
        flash(f"Failed to deny/delete user ID {user_id}.", "danger")
    return redirect(url_for('admin_dashboard'))


@bryl.route("/admin/approve_loan/<int:loan_id>", methods=['POST'])
@admin_required
def approve_loan(loan_id):
    loan = LoanModel.query.get(loan_id)
    if not loan:
        flash("Loan application not found.", "danger")
        return redirect(url_for('admin_dashboard'))

    try:
        loan.status = 'Approved'
        db.session.commit()
        flash(f"Loan ID {loan_id} for {loan.borrower.fullname} approved!", "success")
    except Exception:
        db.session.rollback()
        flash(f"Failed to approve loan ID {loan_id}.", "danger")

    return redirect(url_for('admin_dashboard'))


@bryl.route("/admin/deny_loan/<int:loan_id>", methods=['POST'])
@admin_required
def deny_loan(loan_id):
    loan = LoanModel.query.get(loan_id)
    if not loan:
        flash("Loan application not found.", "danger")
        return redirect(url_for('admin_dashboard'))

    try:
        loan.status = 'Denied'
        db.session.commit()
        flash(f"Loan ID {loan_id} for {loan.borrower.fullname} denied.", "warning")
    except Exception:
        db.session.rollback()
        flash(f"Failed to deny loan ID {loan_id}.", "danger")

    return redirect(url_for('admin_dashboard'))


@bryl.route("/admin/approve_payment/<int:payment_id>", methods=['POST'])
@admin_required
def approve_payment(payment_id):
    payment = PaymentModel.query.get(payment_id)
    if not payment:
        flash("Payment request not found.", "danger")
        return redirect(url_for('admin_dashboard'))

    loan = LoanModel.query.get(payment.loan_id)
    if not loan:
        flash("Associated loan not found.", "danger")
        return redirect(url_for('admin_dashboard'))

    try:
        # 1. Update Payment Status to Approved
        payment.status = 'Approved'

        # 2. Update Loan Balance by reducing the payment amount
        loan.balance -= payment.amount

        # 3. Check for Loan Completion
        completion_message = ""
        if loan.balance <= 0:
            loan.balance = 0  # Ensure balance is not negative
            loan.status = 'Completed'
            completion_message = f"Loan ID {loan.id} is now **COMPLETED**."
        else:
            completion_message = f"Remaining Balance on Loan ID {loan.id}: ₱{loan.balance:,.2f}."

        db.session.commit()
        flash(
            f"Payment ID {payment_id} (₱{payment.amount:,.2f}) approved. {completion_message}",
            "success")

    except Exception:
        db.session.rollback()
        flash(f"Failed to approve payment ID {payment_id}.", "danger")

    return redirect(url_for('admin_dashboard'))


# --- Admin View All Pages ---

@bryl.route("/admin/users")
@admin_required
def view_all_users():
    # Fetch all users, approved and pending
    all_users = UserModel.query.order_by(UserModel.id.asc()).all()
    return render_template("admin_view_all_users.html", all_users=all_users)


@bryl.route("/admin/loans")
@admin_required
def view_all_loans():
    # Fetch all loans and eager load the borrower's full name
    all_loans = LoanModel.query.options(joinedload(LoanModel.borrower)).order_by(
        LoanModel.application_date.desc()).all()
    return render_template("admin_view_all_loans.html", all_loans=all_loans)


@bryl.route("/admin/payments")
@admin_required
def view_all_payments():
    # Fetch all payments and eager load the borrower's full name
    all_payments = PaymentModel.query.options(joinedload(PaymentModel.borrower)).order_by(
        PaymentModel.payment_date.desc()).all()
    return render_template("admin_view_all_payments.html", all_payments=all_payments)


# --- INITIAL SETUP ---

@bryl.cli.command("init-db")
def init_db():
    """Initializes the database and creates the tables."""
    with bryl.app_context():
        # Drop and create all tables (DANGER: WILL DELETE ALL DATA)
        db.drop_all()
        db.create_all()
        print("Database initialized and tables created.")

        # Create an initial Admin user for testing
        if not user_repo.get_user_by_email("admin@test.com"):
            user_repo.create_user("Admin User", "admin@test.com", "password", "Admin")
            print("Default Admin user 'admin@test.com' created with password 'password'.")


# ------------------------------------------------------------------
# --- MAIN EXECUTION ---
# ------------------------------------------------------------------
if __name__ == "__main__":
    # Ensure the database context is active for initial setup or immediate use
    with bryl.app_context():
        db.create_all()  # Ensure tables exist on run if they don't already

    # Run the Flask app
    bryl.run(debug=True)