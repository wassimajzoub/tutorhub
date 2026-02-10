from datetime import datetime, date, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from database.db import db
from database.models import User, Session, Student
from scheduling.utils import get_available_slots

booking_bp = Blueprint('booking', __name__)


@booking_bp.route('/book/<slug>')
def public_profile(slug):
    tutor = User.query.filter_by(profile_slug=slug, is_active=True).first_or_404()
    today = date.today()
    # Show next 21 days
    dates = [today + timedelta(days=i) for i in range(21)]
    return render_template('booking/public.html',
        tutor=tutor,
        dates=dates,
        durations=tutor.duration_list(),
    )


@booking_bp.route('/api/slots/<int:tutor_id>/<date_str>')
def api_slots(tutor_id, date_str):
    """AJAX endpoint: return available slots for a tutor on a given date."""
    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Invalid date'}), 400

    duration = request.args.get('duration', 60, type=int)
    tutor = User.query.get_or_404(tutor_id)

    slots = get_available_slots(tutor_id, target_date, duration)

    return jsonify({
        'date': date_str,
        'duration': duration,
        'slots': [s.strftime('%H:%M') for s in slots],
    })


@booking_bp.route('/book/<slug>/confirm', methods=['POST'])
def confirm_booking(slug):
    tutor = User.query.filter_by(profile_slug=slug, is_active=True).first_or_404()

    student_name = request.form.get('student_name', '').strip()
    parent_email = request.form.get('parent_email', '').strip()
    parent_phone = request.form.get('parent_phone', '').strip()
    subject = request.form.get('subject', '').strip()
    session_type = request.form.get('session_type', 'online')
    duration = int(request.form.get('duration', 60))
    date_str = request.form.get('date', '')
    time_str = request.form.get('time', '')

    if not student_name or not date_str or not time_str:
        flash('Please fill in all required fields.', 'error')
        return redirect(url_for('booking.public_profile', slug=slug))

    try:
        scheduled_at = datetime.strptime(f'{date_str} {time_str}', '%Y-%m-%d %H:%M')
    except ValueError:
        flash('Invalid date or time selected.', 'error')
        return redirect(url_for('booking.public_profile', slug=slug))

    # Check if slot is still available
    target_date = scheduled_at.date()
    available = get_available_slots(tutor.id, target_date, duration)
    slot_times = [s.strftime('%H:%M') for s in available]
    if time_str not in slot_times:
        flash('Sorry, that time slot is no longer available. Please pick another.', 'error')
        return redirect(url_for('booking.public_profile', slug=slug))

    # Try to match to existing student
    student = Student.query.filter_by(
        user_id=tutor.id,
        parent_email=parent_email,
        is_active=True,
    ).first() if parent_email else None

    session = Session(
        user_id=tutor.id,
        student_id=student.id if student else None,
        guest_student_name=student_name,
        guest_parent_email=parent_email,
        guest_parent_phone=parent_phone,
        guest_subject=subject,
        scheduled_at=scheduled_at,
        duration_minutes=duration,
        session_type=session_type,
        rate_charged=tutor.hourly_rate * (duration / 60),
        location=tutor.address if session_type == 'in_person' else '',
    )
    db.session.add(session)
    db.session.commit()

    return render_template('booking/confirmation.html',
        tutor=tutor,
        session=session,
        student_name=student_name,
    )
