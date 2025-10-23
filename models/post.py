from .db import db
from datetime import datetime
from flask import current_app
from sqlalchemy import desc, func

# -----------------------------------------------------------
# 1. SQLAlchemy Model Definitions
# -----------------------------------------------------------

class PostModel(db.Model):
    __tablename__ = 'post'
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) # Foreign key to the user table

    def __repr__(self):
        return f"Post('{self.content[:20]}...', 'User ID: {self.user_id}')"

class LoanModel(db.Model):
    __tablename__ = 'loan'
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    interest_rate = db.Column(db.Float, nullable=False)
    term_months = db.Column(db.Integer, nullable=False)
    balance = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), default='Pending', nullable=False)
    application_date = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # Relationship to payments made on this loan
    payments = db.relationship('PaymentModel', backref='loan_paid', lazy=True)

    def __repr__(self):
        return f"Loan('{self.id}', 'Amount: {self.amount}', 'Status: {self.status}')"


class PaymentModel(db.Model):
    __tablename__ = 'payment'
    id = db.Column(db.Integer, primary_key=True)
    loan_id = db.Column(db.Integer, db.ForeignKey('loan.id'), nullable=False)
    # This links the payment to the user who made it (the borrower)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    method = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(50), default='Pending', nullable=False)
    payment_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    borrower = db.relationship('UserModel', backref=db.backref('payments', lazy=True), foreign_keys=[user_id])

    def __repr__(self):
        return f"Payment('{self.id}', 'Amount: {self.amount}', 'Loan ID: {self.loan_id}', 'Status: {self.status}')"


# -----------------------------------------------------------
# 2. Repository Class (All methods checked for app_context)
# -----------------------------------------------------------

class Post:
    def __init__(self, db_connection):
        self.db = db_connection

    def create_post(self, content, user_id):
        new_post = PostModel(content=content, user_id=user_id)
        with current_app.app_context():
            try:
                db.session.add(new_post)
                db.session.commit()
                return True
            except Exception as e:
                current_app.logger.error(f"Error creating post: {e}")
                db.session.rollback()
                return False

    def get_post_by_id(self, post_id):
        with current_app.app_context():
            return PostModel.query.get(post_id)

    def get_all_posts(self):
        with current_app.app_context():
            return PostModel.query.order_by(desc(PostModel.created_at)).all()

    def update_post(self, post_id, content):
        with current_app.app_context():
            post = self.get_post_by_id(post_id)
            if not post: return False

            post.content = content
            try:
                db.session.commit()
                return True
            except Exception as e:
                current_app.logger.error(f"Error updating post: {e}")
                db.session.rollback()
                return False

    def delete_post(self, post_id):
        with current_app.app_context():
            post = self.get_post_by_id(post_id)
            if not post: return False

            try:
                db.session.delete(post)
                db.session.commit()
                return True
            except Exception as e:
                current_app.logger.error(f"Error deleting post: {e}")
                db.session.rollback()
                return False