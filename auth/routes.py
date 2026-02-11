import re
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from database.db import db
from database.models import User

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


def slugify(text):
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    return text


@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        full_name = request.form.get('full_name', '').strip()

        if not email or not password or not full_name:
            flash('All fields are required.', 'error')
            return render_template('auth/signup.html')

        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'error')
            return render_template('auth/signup.html')

        if User.query.filter_by(email=email).first():
            flash('An account with this email already exists.', 'error')
            return render_template('auth/signup.html')

        # Generate unique slug
        base_slug = slugify(full_name)
        slug = base_slug
        counter = 1
        while User.query.filter_by(profile_slug=slug).first():
            slug = f'{base_slug}-{counter}'
            counter += 1

        user = User(email=email, full_name=full_name, profile_slug=slug)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        login_user(user)
        flash('Welcome to TutorHub! Complete your profile to get started.', 'success')
        return redirect(url_for('auth.profile'))

    return render_template('auth/signup.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard.index'))

        flash('Invalid email or password.', 'error')

    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('auth.login'))


@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.full_name = request.form.get('full_name', '').strip()
        current_user.bio = request.form.get('bio', '').strip()
        current_user.subjects = request.form.get('subjects', '').strip()
        current_user.hourly_rate = float(request.form.get('hourly_rate', 0) or 0)
        current_user.currency = request.form.get('currency', 'USD').strip()
        current_user.timezone = request.form.get('timezone', 'America/New_York').strip()
        current_user.phone = request.form.get('phone', '').strip()
        current_user.address = request.form.get('address', '').strip()
        current_user.session_durations = request.form.get('session_durations', '60').strip()

        new_slug = request.form.get('profile_slug', '').strip()
        if new_slug and new_slug != current_user.profile_slug:
            new_slug = slugify(new_slug)
            existing = User.query.filter_by(profile_slug=new_slug).first()
            if existing and existing.id != current_user.id:
                flash('That profile URL is already taken.', 'error')
                return render_template('auth/profile.html')
            current_user.profile_slug = new_slug

        db.session.commit()
        flash('Profile updated!', 'success')
        return redirect(url_for('auth.profile'))

    return render_template('auth/profile.html')
