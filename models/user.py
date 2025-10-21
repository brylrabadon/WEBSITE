# user.py (FINAL FIXED VERSION)

from .db import db # Use relative import if in 'models' folder
from werkzeug.security import generate_password_hash, check_password_hash
from flask import current_app
from sqlalchemy import desc


# -----------------------------------------------------------
# 1. SQLAlchemy Model Definition (The ORM table structure)
# -----------------------------------------------------------
class UserModel(db.Model):
    __tablename__ = 'user' # Ensures table name is lowercase 'user'

    id = db.Column(db.Integer, primary_key=True)
    fullname = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(50), nullable=False)
    is_approved = db.Column(db.Boolean, default=False, nullable=False) # The column that was missing

    # Relationships to models defined in post.py
    posts = db.relationship('PostModel', backref='author', lazy=True)
    loans = db.relationship('LoanModel', backref='borrower', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"User('{self.fullname}', '{self.email}', '{self.role}')"


# -----------------------------------------------------------
# 2. Repository Class (All DB operations wrapped in app_context)
# -----------------------------------------------------------
class User:
    def __init__(self, db_connection):
        self.db = db_connection

    def create_user(self, fullname, email, password, role="user"):
        new_user = UserModel(fullname=fullname, email=email, role=role)
        new_user.set_password(password)

        with current_app.app_context(): # FIX: Added app_context
            try:
                db.session.add(new_user)
                db.session.commit()
                return True
            except Exception as e:
                current_app.logger.error(f"Error creating user: {e}")
                db.session.rollback()
                return False

    def get_user_by_id(self, user_id):
        with current_app.app_context(): # FIX: Added app_context
            return UserModel.query.get(user_id)

    def get_user_by_email(self, email):
        with current_app.app_context(): # FIX: Added app_context
            return UserModel.query.filter_by(email=email).first()

    def get_all_users(self):
        with current_app.app_context(): # FIX: Added app_context
            return UserModel.query.order_by(desc(UserModel.id)).all()

    def update_user(self, user_id, fullname=None, email=None, password=None, is_approved=None):
        with current_app.app_context(): # FIX: Added app_context
            user = UserModel.query.get(user_id) # Using query inside context
            if not user: return False

            updated = False
            # ... (rest of the update logic)
            if fullname is not None:
                user.fullname = fullname
                updated = True
            if email is not None:
                user.email = email
                updated = True
            if password is not None:
                user.set_password(password)
                updated = True
            if is_approved is not None:
                user.is_approved = is_approved
                updated = True

            if updated:
                try:
                    db.session.commit()
                    return True
                except Exception as e:
                    current_app.logger.error(f"Error updating user: {e}")
                    db.session.rollback()
                    return False
            return False

    def delete_user(self, user_id):
        with current_app.app_context(): # FIX: Added app_context
            user = UserModel.query.get(user_id) # Using query inside context
            if not user: return False

            try:
                db.session.delete(user)
                db.session.commit()
                return True
            except Exception as e:
                current_app.logger.error(f"Error deleting user: {e}")
                db.session.rollback()
                return False