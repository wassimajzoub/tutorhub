from datetime import datetime, time
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from database.db import db


class User(UserMixin, db.Model):
    """Tutor account."""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    bio = db.Column(db.Text, default='')
    subjects = db.Column(db.String(250), default='')          # comma-separated
    hourly_rate = db.Column(db.Float, default=0.0)
    currency = db.Column(db.String(3), default='USD')
    timezone = db.Column(db.String(50), default='America/New_York')
    phone = db.Column(db.String(30), default='')
    address = db.Column(db.String(250), default='')            # for in-person sessions
    profile_slug = db.Column(db.String(80), unique=True, index=True)
    session_durations = db.Column(db.String(50), default='60') # comma-separated minutes
    default_meeting_link = db.Column(db.String(500), default='')  # Google Meet/Zoom link
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    students = db.relationship('Student', backref='tutor', lazy='dynamic')
    availabilities = db.relationship('Availability', backref='tutor', lazy='dynamic')
    sessions = db.relationship('Session', backref='tutor', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def subject_list(self):
        return [s.strip() for s in self.subjects.split(',') if s.strip()]

    def duration_list(self):
        return [int(d.strip()) for d in self.session_durations.split(',') if d.strip()]


class Student(db.Model):
    __tablename__ = 'students'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    parent_name = db.Column(db.String(120), default='')
    parent_email = db.Column(db.String(120), default='')
    parent_phone = db.Column(db.String(30), default='')
    grade_level = db.Column(db.String(30), default='')
    subject = db.Column(db.String(120), default='')
    notes = db.Column(db.Text, default='')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    sessions = db.relationship('Session', backref='student', lazy='dynamic')


class Availability(db.Model):
    """Weekly recurring availability slots."""
    __tablename__ = 'availabilities'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    day_of_week = db.Column(db.Integer, nullable=False)  # 0=Mon, 6=Sun
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    is_active = db.Column(db.Boolean, default=True)


class Session(db.Model):
    """A tutoring session."""
    __tablename__ = 'sessions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=True)
    # For public bookings where student isn't in system yet
    guest_student_name = db.Column(db.String(120), default='')
    guest_parent_email = db.Column(db.String(120), default='')
    guest_parent_phone = db.Column(db.String(30), default='')
    guest_subject = db.Column(db.String(120), default='')

    scheduled_at = db.Column(db.DateTime, nullable=False, index=True)
    duration_minutes = db.Column(db.Integer, default=60)
    session_type = db.Column(db.String(20), default='online')  # online / in_person
    meeting_link = db.Column(db.String(500), default='')
    location = db.Column(db.String(250), default='')
    rate_charged = db.Column(db.Float, default=0.0)

    status = db.Column(db.String(20), default='scheduled')  # scheduled/completed/cancelled/no_show
    notes = db.Column(db.Text, default='')
    homework = db.Column(db.Text, default='')
    progress_rating = db.Column(db.Integer, nullable=True)   # 1-5

    is_paid = db.Column(db.Boolean, default=False)
    paid_date = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    def student_display_name(self):
        if self.student:
            return self.student.name
        return self.guest_student_name or 'Unknown'

    def contact_email(self):
        if self.student:
            return self.student.parent_email
        return self.guest_parent_email


class Invoice(db.Model):
    __tablename__ = 'invoices'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=True)
    invoice_number = db.Column(db.String(30), unique=True, nullable=False)
    session_ids = db.Column(db.Text, default='')   # comma-separated session IDs
    total_amount = db.Column(db.Float, default=0.0)
    is_paid = db.Column(db.Boolean, default=False)
    generated_date = db.Column(db.DateTime, default=datetime.utcnow)
    due_date = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, default='')
