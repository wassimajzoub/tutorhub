from datetime import datetime, time, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from database.db import db
from database.models import Availability, Session, Student
from scheduling.utils import DAY_NAMES, format_availability

scheduling_bp = Blueprint('scheduling', __name__, url_prefix='/scheduling')


@scheduling_bp.route('/availability', methods=['GET', 'POST'])
@login_required
def availability():
    if request.method == 'POST':
        # Clear existing availability
        Availability.query.filter_by(user_id=current_user.id).delete()

        for i in range(7):
            if request.form.get(f'day_{i}_enabled'):
                start_str = request.form.get(f'day_{i}_start', '')
                end_str = request.form.get(f'day_{i}_end', '')
                if start_str and end_str:
                    try:
                        start = datetime.strptime(start_str, '%H:%M').time()
                        end = datetime.strptime(end_str, '%H:%M').time()
                        if end > start:
                            avail = Availability(
                                user_id=current_user.id,
                                day_of_week=i,
                                start_time=start,
                                end_time=end,
                            )
                            db.session.add(avail)
                    except ValueError:
                        continue

        db.session.commit()
        flash('Availability updated!', 'success')
        return redirect(url_for('scheduling.availability'))

    current_avail = Availability.query.filter_by(
        user_id=current_user.id, is_active=True
    ).all()

    # Build a dict for the template
    avail_dict = {}
    for a in current_avail:
        avail_dict[a.day_of_week] = {
            'enabled': True,
            'start': a.start_time.strftime('%H:%M'),
            'end': a.end_time.strftime('%H:%M'),
        }

    return render_template('scheduling/availability.html',
        day_names=DAY_NAMES,
        avail_dict=avail_dict,
    )


@scheduling_bp.route('/sessions')
@login_required
def sessions_list():
    now = datetime.utcnow()
    view = request.args.get('view', 'upcoming')

    if view == 'past':
        sessions = Session.query.filter(
            Session.user_id == current_user.id,
            Session.scheduled_at < now,
        ).order_by(Session.scheduled_at.desc()).limit(50).all()
    else:
        sessions = Session.query.filter(
            Session.user_id == current_user.id,
            Session.scheduled_at >= now,
            Session.status != 'cancelled',
        ).order_by(Session.scheduled_at).all()

    return render_template('scheduling/sessions.html', sessions=sessions, view=view)


@scheduling_bp.route('/sessions/add', methods=['GET', 'POST'])
@login_required
def add_session():
    if request.method == 'POST':
        student_id = request.form.get('student_id')
        date_str = request.form.get('date', '')
        time_str = request.form.get('time', '')
        duration = int(request.form.get('duration', 60))
        session_type = request.form.get('session_type', 'online')

        try:
            scheduled_at = datetime.strptime(f'{date_str} {time_str}', '%Y-%m-%d %H:%M')
        except ValueError:
            flash('Invalid date or time.', 'error')
            return redirect(url_for('scheduling.add_session'))

        session = Session(
            user_id=current_user.id,
            student_id=int(student_id) if student_id else None,
            scheduled_at=scheduled_at,
            duration_minutes=duration,
            session_type=session_type,
            rate_charged=current_user.hourly_rate * (duration / 60),
            meeting_link=request.form.get('meeting_link', '').strip(),
            location=request.form.get('location', '').strip(),
        )
        db.session.add(session)
        db.session.commit()
        flash('Session scheduled!', 'success')
        return redirect(url_for('scheduling.sessions_list'))

    students = Student.query.filter_by(
        user_id=current_user.id, is_active=True
    ).order_by(Student.name).all()

    return render_template('scheduling/session_form.html',
        session=None,
        students=students,
        durations=current_user.duration_list(),
        action='Schedule',
    )


@scheduling_bp.route('/sessions/<int:session_id>', methods=['GET', 'POST'])
@login_required
def session_detail(session_id):
    session = Session.query.filter_by(id=session_id, user_id=current_user.id).first_or_404()

    if request.method == 'POST':
        action = request.form.get('action', '')

        if action == 'complete':
            session.status = 'completed'
            session.completed_at = datetime.utcnow()
            session.notes = request.form.get('notes', '').strip()
            session.homework = request.form.get('homework', '').strip()
            rating = request.form.get('progress_rating')
            session.progress_rating = int(rating) if rating else None
            db.session.commit()
            flash('Session marked as completed!', 'success')

        elif action == 'cancel':
            session.status = 'cancelled'
            db.session.commit()
            flash('Session cancelled.', 'success')

        elif action == 'update_notes':
            session.notes = request.form.get('notes', '').strip()
            session.homework = request.form.get('homework', '').strip()
            rating = request.form.get('progress_rating')
            session.progress_rating = int(rating) if rating else None
            db.session.commit()
            flash('Notes updated!', 'success')

        elif action == 'mark_paid':
            session.is_paid = True
            session.paid_date = datetime.utcnow()
            db.session.commit()
            flash('Marked as paid!', 'success')

        elif action == 'mark_unpaid':
            session.is_paid = False
            session.paid_date = None
            db.session.commit()
            flash('Marked as unpaid.', 'success')

        return redirect(url_for('scheduling.session_detail', session_id=session.id))

    return render_template('scheduling/session_detail.html', session=session)
