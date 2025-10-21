# bryl.py (FINAL VERIFIED VERSION)

from flask import Flask, render_template, request, redirect, session, url_for, flash
from flask_sqlalchemy import SQLAlchemy
import os
# Imports models from the 'models' directory (assuming structure: bryl.py, models/db.py, models/user.py, etc.)
from models.db import db
from models.user import User, UserModel
from models.post import Post, PostModel, LoanModel

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


# --- ROUTES ---
@bryl.route("/")
def home():
    if 'email' in session:
        return redirect(url_for('dashboard'))
    return render_template("index.html")


@bryl.route("/about")
def about():
    return render_template("about.html")


@bryl.route("/contact")
def contact():
    return render_template("contact.html")


@bryl.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        fullname = request.form["fullname"]
        email = request.form["email"]
        password = request.form["password"]
        confirm = request.form["confirm_password"]
        role = request.form["role"]

        if password != confirm:
            return render_template("register.html", error="Passwords do not match!")

        if user_repo.get_user_by_email(email):
            return render_template("register.html", error="Email already exists!")

        # Create user (is_approved=False by default)
        success = user_repo.create_user(fullname, email, password, role)

        if success:
            flash("Registration successful! Your account is pending admin approval before you can log in.", "success")
            return redirect(url_for("home"))
        else:
            flash("Registration failed due to a database error.", "danger")
            return redirect(url_for("register"))

    return render_template("register.html")


@bryl.route("/login", methods=["POST"])
def login():
    # --- Code to retrieve user data and object ---
    email = request.form["email"]
    password = request.form["password"]
    user = user_repo.get_user_by_email(email)
    # ---------------------------------------------

    if user and user.check_password(password):
        # 1. Check for approval
        if not user.is_approved:
            flash("Your account is pending administrator approval. Please wait.", "warning")
            return redirect(url_for("home"))

        # 2. Log in successful
        session["email"] = user.email
        session["role"] = user.role
        session["fullname"] = user.fullname

        # 3. Check role and redirect
        # IMPORTANT: Use 'Admin' (capital A) because that is how it is set in register.html
        if user.role == 'Admin':
            return redirect(url_for('admin_dashboard'))

        return redirect(url_for("dashboard"))
    else:
        flash("Invalid email or password.", "danger")
        return redirect(url_for("home"))


@bryl.route('/dashboard')
def dashboard():
    # **THIS SECTION WAS RE-ADDED/VERIFIED**
    if "email" not in session:
        return redirect(url_for('home'))

    fullname = session.get('fullname', 'User')
    role = session.get('role', 'Guest')

    # Fetch all posts (This requires post.py to have app_context fixes)
    all_posts = post_repo.get_all_posts()

    return render_template("dashboard.html", fullname=fullname, role=role, all_posts=all_posts)


# --- ADMIN ROUTES ---

# 1. Admin Dashboard Route
@bryl.route('/admin')
def admin_dashboard():
    # Role check: Ensure only 'Admin' role can view this page
    # IMPORTANT: Use 'Admin' (capital A) for comparison to match register.html
    if 'role' not in session or session['role'] != 'Admin':
        flash("Access denied. You do not have administrator privileges.", "danger")
        return redirect(url_for('home'))

    all_users = user_repo.get_all_users()

    with bryl.app_context():
        # Fetch all pending loans
        pending_loans = LoanModel.query.filter_by(status='Pending').all()

    return render_template("admin_dashboard.html", users=all_users, pending_loans=pending_loans)


# 2. Approve User Account Route
@bryl.route('/admin/approve_user/<int:user_id>', methods=['POST'])
def approve_user(user_id):
    # IMPORTANT: Use 'Admin' (capital A) for comparison
    if 'role' not in session or session['role'] != 'Admin':
        flash("Permission denied.", "danger")
        return redirect(url_for('dashboard'))

    success = user_repo.update_user(user_id, is_approved=True)

    if success:
        flash(f"Account for User ID {user_id} has been approved. They can now log in.", "success")
    else:
        flash(f"Failed to approve user ID {user_id}. Check logs.", "danger")

    return redirect(url_for('admin_dashboard'))


# 3. Approve Loan Route
@bryl.route('/admin/approve_loan/<int:loan_id>', methods=['POST'])
def approve_loan(loan_id):
    # IMPORTANT: Use 'Admin' (capital A) for comparison
    if 'role' not in session or session['role'] != 'Admin':
        flash("Permission denied.", "danger")
        return redirect(url_for('dashboard'))

    with bryl.app_context():
        loan = LoanModel.query.get(loan_id)
        if loan:
            loan.status = 'Approved'
            try:
                db.session.commit()
                flash(f"Loan ID {loan_id} has been approved.", "success")
            except Exception:
                db.session.rollback()
                flash(f"Failed to approve loan ID {loan_id}.", "danger")
        else:
            flash("Loan not found.", "danger")

    return redirect(url_for('admin_dashboard'))

@bryl.route("/forgot_password")
def forgot_password():
    return render_template("forgot_password.html")


@bryl.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


# --- MAIN EXECUTION ---
if __name__ == "__main__":
    with bryl.app_context():
        # This will create the database file and tables if they don't exist
        db.create_all()
    bryl.run(debug=True)