from flask import Flask, render_template, request, redirect, session, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
import os

# --- APP CONFIGURATION ---
bryl = Flask(__name__)
bryl.secret_key = "bryl_secret_key"

# Database setup (SQLite)
bryl.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///loansystem.db"
bryl.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(bryl)

# --- DATABASE MODELS ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fullname = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(50), nullable=False)  # "Admin" or "Borrower"

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


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

        # Validation
        if password != confirm:
            return render_template("register.html", error="Passwords do not match!")

        user = User.query.filter_by(email=email).first()
        if user:
            return render_template("register.html", error="Email already exists!")

        # Save new user
        new_user = User(fullname=fullname, email=email, role=role)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        session["email"] = email
        session["role"] = role
        return redirect(url_for("dashboard"))
    return render_template("register.html")


@bryl.route("/login", methods=["POST"])
def login():
    email = request.form["email"]
    password = request.form["password"]

    user = User.query.filter_by(email=email).first()
    if user and user.check_password(password):
        session["email"] = user.email
        session["role"] = user.role
        session["fullname"] = user.fullname
        return redirect(url_for("dashboard"))
    else:
        flash("Invalid email or password.")
        return redirect(url_for("home"))


@bryl.route("/dashboard")
def dashboard():
    if "email" not in session:
        return redirect(url_for("home"))
    return render_template("dashboard.html", fullname=session["fullname"], role=session["role"])


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
        db.create_all()
    bryl.run(debug=True)
