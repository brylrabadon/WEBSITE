# bryl.py (FINAL, COMPLETE, and FIXED CODE)

from flask import Flask, render_template, request, redirect, session, url_for, flash
from flask_sqlalchemy import SQLAlchemy
import os
from datetime import datetime
from sqlalchemy.orm import joinedload  # Import for eager loading
from models.db import db
from models.user import User, UserModel
# CRITICAL: Ensure all Models are imported here
from models.post import Post, PostModel, LoanModel, PaymentModel

bryl = Flask(__name__)
bryl.secret_key = "bryl_secret_key"

# Database setup (SQLite)
bryl.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///loansystem.db"
bryl.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize db *with* the app instance
db.init_app(bryl)

# Initialize the User and Post repositories
user_repo = User(None)
post_repo = Post(None)


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


# FIX: Added the essential /register route
@bryl.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        fullname = request.form["fullname"]
        email = request.form["email"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]
        role = request.form.get("role", "Borrower")  # Default to Borrower

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("register"))

        # user_repo.create_user handles password hashing and setting is_approved=False
        success = user_repo.create_user(fullname, email, password, role)

        if success:
            flash("Registration successful! Your account is awaiting administrator approval before you can log in.",
                  "success")
            return redirect(url_for("home"))
        else:
            flash("Registration failed. This email may already be registered.", "danger")
            return redirect(url_for("register"))

    return render_template("register.html")


@bryl.route("/login", methods=["POST"])
def login():
    email = request.form["email"]
    password = request.form["password"]
    user = user_repo.get_user_by_email(email)

    if user and user.check_password(password):
        # 1. Check for approval
        if not user.is_approved:
            flash("Your account is pending administrator approval. Please wait.", "warning")
            return redirect(url_for("home"))

        # 2. Log in successful
        session["email"] = user.email
        session["role"] = user.role
        session["fullname"] = user.fullname
        session["user_id"] = user.id

        # 3. Check role and redirect
        if user.role == 'Admin':
            return redirect(url_for('admin_dashboard'))

        return redirect(url_for("dashboard"))
    else:
        flash("Invalid email or password.", "danger")
        return redirect(url_for("home"))


@bryl.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    # FIX: Removed duplicate /logout route
    return redirect(url_for("home"))


@bryl.route('/about')
def about():
    return render_template('about.html')


@bryl.route('/contact')
def contact():
    return render_template('contact.html')


@bryl.route("/forgot_password")
def forgot_password():
    return render_template("forgot_password.html")


# ------------------------------------------------------------------
# --- BORROWER ROUTES ---
# ------------------------------------------------------------------

# FIX: Added the essential /dashboard route
@bryl.route("/dashboard")
def dashboard():
    if 'user_id' not in session:
        flash("Please log in to access your dashboard.", "warning")
        return redirect(url_for("home"))

    user_id = session['user_id']

    with bryl.app_context():
        # Fetch active/pending loans for the user
        user_loans = LoanModel.query.filter(
            LoanModel.user_id == user_id,
            # Show all non-completed loans: Pending, Approved, Rejected
            LoanModel.status != 'Completed'
        ).all()

        # Fetch approved payments for the user (history)
        user_payments = PaymentModel.query.filter(
            PaymentModel.user_id == user_id,
            PaymentModel.status == 'Approved'
        ).order_by(PaymentModel.payment_date.desc()).all()

    return render_template("dashboard.html",
                           fullname=session.get('fullname'),
                           role=session.get('role'),
                           user_loans=user_loans,
                           user_payments=user_payments)


# FIX: Added the essential /apply_loan route
@bryl.route("/apply_loan", methods=["GET", "POST"])
def apply_loan():
    if 'user_id' not in session:
        flash("Please log in to apply for a loan.", "warning")
        return redirect(url_for("home"))

    if request.method == "POST":
        try:
            user_id = session['user_id']
            amount = float(request.form["amount"])
            interest_rate = float(request.form["interest_rate"])
            term_months = int(request.form["term_months"])

            # post_repo.create_loan is assumed to exist and set initial balance = amount
            success = post_repo.create_loan(user_id, amount, interest_rate, term_months)

            if success:
                flash("Loan application submitted successfully and is awaiting administrator approval.", "success")
                return redirect(url_for("dashboard"))
            else:
                flash("Loan application failed. Please try again.", "danger")

        except ValueError:
            flash("Invalid input. Please ensure all fields are numbers.", "danger")
        except Exception as e:
            flash(f"An unexpected error occurred. {e}", "danger")

        return redirect(url_for("apply_loan"))

    return render_template("apply_loan.html", fullname=session.get('fullname'))


# FIX: Added the essential /payment route (Make a Payment Request)
@bryl.route("/payment", methods=["GET", "POST"])
def payment():
    if 'user_id' not in session:
        flash("Please log in to make a payment.", "warning")
        return redirect(url_for("home"))

    user_id = session['user_id']

    if request.method == "POST":
        try:
            loan_id = int(request.form["loan_id"])
            amount = float(request.form["amount"])
            method = request.form["method"]

            with bryl.app_context():
                loan = LoanModel.query.get(loan_id)

            if not loan or loan.user_id != user_id or loan.status != 'Approved':
                flash("Invalid or non-approved loan selected.", "danger")
                return redirect(url_for("payment"))

            if amount <= 0:
                flash("Payment amount must be greater than zero.", "danger")
                return redirect(url_for("payment"))

            if amount > loan.balance:
                flash(f"Payment amount (₱{amount:,.2f}) exceeds remaining loan balance (₱{loan.balance:,.2f}).",
                      "danger")
                return redirect(url_for("payment"))

            # post_repo.create_payment is assumed to exist. Status will be 'Pending'
            success = post_repo.create_payment(user_id, loan_id, amount, method)

            if success:
                flash("Payment successfully submitted and is awaiting administrator approval.", "success")
                return redirect(url_for("dashboard"))
            else:
                flash("Payment submission failed. Please try again.", "danger")

        except ValueError:
            flash("Invalid input. Please check loan ID and amount.", "danger")
        except Exception:
            flash("An unexpected error occurred during payment submission.", "danger")

        return redirect(url_for("payment"))

    # GET request - Show active loan options for payment
    with bryl.app_context():
        active_loans = LoanModel.query.filter(
            LoanModel.user_id == user_id,
            LoanModel.status == 'Approved'
        ).all()

    return render_template("payment.html", active_loans=active_loans)


# FIX: Added the essential /update_profile route
@bryl.route("/update_profile", methods=["GET", "POST"])
def update_profile():
    if 'user_id' not in session:
        flash("Please log in to update your profile.", "warning")
        return redirect(url_for("home"))

    user_id = session['user_id']

    if request.method == "POST":
        fullname = request.form["fullname"]
        email = request.form["email"]
        # Allow password to be empty if not changing it
        password = request.form["password"] if request.form["password"] else None

        # user_repo.update_user handles the update logic.
        success = user_repo.update_user(user_id, fullname=fullname, email=email, password=password)

        if success:
            # Update session variables if email or name changed
            session["fullname"] = fullname
            session["email"] = email
            flash("Profile updated successfully.", "success")
        else:
            flash("Profile update failed. Email may already be in use.", "danger")

        return redirect(url_for("update_profile"))

    # GET request - Fetch current user data to pre-fill the form
    with bryl.app_context():
        user = UserModel.query.get(user_id)

    return render_template("update_profile.html", user=user)


# ------------------------------------------------------------------
# --- ADMIN ROUTES ---
# ------------------------------------------------------------------

@bryl.route('/admin')
@bryl.route('/admin_dashboard')
def admin_dashboard():
    if 'role' not in session or session['role'] != 'Admin':
        flash("Access denied.", "danger")
        return redirect(url_for('home'))

    fullname = session.get('fullname', 'Admin')

    with bryl.app_context():
        # Pending lists for approval tables
        pending_users = UserModel.query.filter_by(is_approved=False).all()

        # FIX 1: Eagerly load the borrower for pending loans
        pending_loans = LoanModel.query.filter_by(status='Pending').options(joinedload(LoanModel.borrower)).all()

        # CRITICAL FIX for previous 'NoneType' error: Use joinedload for borrower info
        pending_payments = PaymentModel.query.filter_by(status='Pending') \
            .options(joinedload(PaymentModel.borrower)).all()

        # All lists for general overview/links
        all_users = UserModel.query.all()

        # FIX 2: Eagerly load the borrower for all loans list
        all_loans = LoanModel.query.options(joinedload(LoanModel.borrower)).all()

        # FIX 3: Eagerly load the borrower for all payments list
        all_payments = PaymentModel.query.options(joinedload(PaymentModel.borrower)).all()

    return render_template("admin_dashboard.html",
                           fullname=fullname,
                           pending_users=pending_users,
                           pending_loans=pending_loans,
                           pending_payments=pending_payments,
                           user_count=len(all_users),
                           loan_count=len(all_loans),
                           payment_count=len(all_payments))
@bryl.route('/admin/view_all_users')
def view_all_users():
    if 'role' not in session or session['role'] != 'Admin':
        flash("Access denied.", "danger")
        return redirect(url_for('home'))

    with bryl.app_context():
        all_users = UserModel.query.all()

    fullname = session.get('fullname', 'Admin')
    return render_template("admin_view_all_users.html", fullname=fullname, all_users=all_users)


@bryl.route('/admin/view_all_loans')
def view_all_loans():
    if 'role' not in session or session['role'] != 'Admin':
        flash("Access denied.", "danger")
        return redirect(url_for('home'))

    with bryl.app_context():
        # Eager load the borrower for display optimization
        all_loans = LoanModel.query.options(joinedload(LoanModel.borrower)).all()

    fullname = session.get('fullname', 'Admin')
    return render_template("admin_view_all_loans.html", fullname=fullname, all_loans=all_loans)


@bryl.route('/admin/view_all_payments')
def view_all_payments():
    # 1. Authorization Check
    if 'role' not in session or session['role'] != 'Admin':
        flash("Access denied.", "danger")
        return redirect(url_for('home'))

    # 2. Data Fetching
    with bryl.app_context():
        # Eager load the borrower for display optimization
        all_payments = PaymentModel.query.options(joinedload(PaymentModel.borrower)).all()

    fullname = session.get('fullname', 'Admin')
    # 3. Render the correct template, passing the fetched list
    return render_template("admin_view_all_payments.html", fullname=fullname, all_payments=all_payments)



@bryl.route('/admin/approve_user/<int:user_id>', methods=['POST'])
def approve_user(user_id):
    if 'role' not in session or session['role'] != 'Admin':
        flash("Permission denied.", "danger")
        return redirect(url_for('dashboard'))

    # user_repo.update_user handles the approval update
    success = user_repo.update_user(user_id, is_approved=True)

    if success:
        flash(f"Account for User ID {user_id} has been approved. They can now log in.", "success")
    else:
        flash(f"Failed to approve user ID {user_id}. Check logs.", "danger")

    return redirect(url_for('admin_dashboard'))


@bryl.route('/admin/approve_loan/<int:loan_id>', methods=['POST'])
def approve_loan(loan_id):
    if 'role' not in session or session['role'] != 'Admin':
        flash("Permission denied.", "danger")
        return redirect(url_for('dashboard'))

    with bryl.app_context():
        loan = LoanModel.query.get(loan_id)
        if loan:
            loan.status = 'Approved'
            # FIX: Ensure the initial loan balance is set to the amount upon approval,
            # if not already done in create_loan
            if loan.balance is None:
                loan.balance = loan.amount
            try:
                db.session.commit()
                flash(f"Loan ID {loan_id} has been approved.", "success")
            except Exception:
                db.session.rollback()
                flash(f"Failed to approve loan ID {loan_id}.", "danger")
        else:
            flash("Loan not found.", "danger")

    return redirect(url_for('admin_dashboard'))


@bryl.route('/admin/approve_payment/<int:payment_id>', methods=['POST'])
def approve_payment(payment_id):
    if 'role' not in session or session['role'] != 'Admin':
        flash("Permission denied.", "danger")
        return redirect(url_for('dashboard'))

    with bryl.app_context():
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


# --- MAIN EXECUTION ---
if __name__ == "__main__":
    with bryl.app_context():
        db.create_all()
    bryl.run(debug=True)