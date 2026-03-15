from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from sqlalchemy import func, and_
from database.models import Session, Student
from database.db import db

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/dashboard')
@login_required
def index():
    # Redirect to onboarding if not completed
    if not current_user.onboarding_completed:
        return redirect(url_for('onboarding.wizard'))

    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)

    # ── Time-of-day greeting ──
    hour = now.hour
    if hour < 12:
        greeting = 'Good morning'
    elif hour < 17:
        greeting = 'Good afternoon'
    else:
        greeting = 'Good evening'

    first_name = current_user.full_name.split()[0] if current_user.full_name else ''

    # ── Today's sessions (all, non-cancelled) ──
    todays_sessions = Session.query.filter(
        Session.user_id == current_user.id,
        Session.scheduled_at >= today_start,
        Session.scheduled_at < today_end,
        Session.status != 'cancelled',
    ).order_by(Session.scheduled_at).all()

    today_expected = sum(s.rate_charged for s in todays_sessions if s.status == 'scheduled')

    # ── Next upcoming session (now or future) ──
    next_session = Session.query.filter(
        Session.user_id == current_user.id,
        Session.scheduled_at >= now,
        Session.status == 'scheduled',
    ).order_by(Session.scheduled_at).first()

    # Context from last session with the same student
    prev_session_with_student = None
    if next_session and next_session.student_id:
        prev_session_with_student = Session.query.filter(
            Session.user_id == current_user.id,
            Session.student_id == next_session.student_id,
            Session.status == 'completed',
            Session.id != next_session.id,
        ).order_by(Session.scheduled_at.desc()).first()

    # Later today = today's sessions after the next one
    later_today = []
    if next_session:
        later_today = [s for s in todays_sessions if s.id != next_session.id and s.scheduled_at > now]
    else:
        later_today = [s for s in todays_sessions if s.scheduled_at > now]

    # ── Week view: sessions per day (Mon-Sun of current week) ──
    # Find Monday of current week
    days_since_monday = now.weekday()  # 0=Mon
    week_start = (today_start - timedelta(days=days_since_monday))
    week_end = week_start + timedelta(days=7)

    week_sessions = Session.query.filter(
        Session.user_id == current_user.id,
        Session.scheduled_at >= week_start,
        Session.scheduled_at < week_end,
        Session.status != 'cancelled',
    ).order_by(Session.scheduled_at).all()

    # Build week_days: list of {name, short, sessions: [...], is_today}
    day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    week_days = []
    for i in range(7):
        day_date = week_start + timedelta(days=i)
        day_end = day_date + timedelta(days=1)
        day_sessions = [s for s in week_sessions if day_date <= s.scheduled_at < day_end]
        week_days.append({
            'name': day_names[i],
            'date': day_date,
            'sessions': day_sessions,
            'is_today': day_date.date() == now.date(),
        })

    # ── Needs attention ──
    # (a) Unpaid completed sessions
    unpaid_sessions = Session.query.filter(
        Session.user_id == current_user.id,
        Session.status == 'completed',
        Session.is_paid == False,
    ).all()
    unpaid_total = sum(s.rate_charged for s in unpaid_sessions)

    # (b) Recent completed sessions without notes (last 10 completed, no notes)
    no_notes_sessions = Session.query.filter(
        Session.user_id == current_user.id,
        Session.status == 'completed',
        (Session.notes == '') | (Session.notes == None),
    ).order_by(Session.completed_at.desc()).limit(5).all()

    # (c) Inactive students (active students whose last session was >21 days ago)
    active_students = Student.query.filter_by(user_id=current_user.id, is_active=True).all()
    inactive_students = []
    cutoff = now - timedelta(days=21)
    for student in active_students:
        last_session = Session.query.filter(
            Session.user_id == current_user.id,
            Session.student_id == student.id,
            Session.status != 'cancelled',
        ).order_by(Session.scheduled_at.desc()).first()
        if last_session and last_session.scheduled_at < cutoff:
            weeks_ago = (now - last_session.scheduled_at).days // 7
            inactive_students.append({'student': student, 'weeks_ago': weeks_ago})
        elif not last_session:
            # Student exists but has never had a session
            inactive_students.append({'student': student, 'weeks_ago': None})

    # Build attention items (max 5)
    attention_items = []
    if unpaid_sessions:
        attention_items.append({
            'type': 'unpaid',
            'icon': 'circle-dollar-sign',
            'color': 'orange',
            'text': f'{len(unpaid_sessions)} unpaid session{"s" if len(unpaid_sessions) != 1 else ""} (${unpaid_total:,.0f})',
            'url': url_for('payments.overview'),
        })
    for s in no_notes_sessions[:2]:
        attention_items.append({
            'type': 'notes',
            'icon': 'file-text',
            'color': 'blue',
            'text': f'{s.student_display_name()} — session missing notes',
            'url': url_for('scheduling.session_detail', session_id=s.id),
        })
    for info in inactive_students[:2]:
        st = info['student']
        if info['weeks_ago']:
            attention_items.append({
                'type': 'inactive',
                'icon': 'user-x',
                'color': 'purple',
                'text': f'{st.name} — no session in {info["weeks_ago"]}w',
                'url': url_for('students.detail', student_id=st.id),
            })

    attention_items = attention_items[:5]

    # ── Student pulse ──
    student_pulse = []
    for student in active_students:
        completed = Session.query.filter(
            Session.user_id == current_user.id,
            Session.student_id == student.id,
            Session.status == 'completed',
        ).order_by(Session.scheduled_at.desc()).all()

        total_count = len(completed)
        rated = [s for s in completed if s.progress_rating is not None]

        avg_rating = None
        trend = 'neutral'  # up, down, neutral
        if rated:
            avg_rating = sum(s.progress_rating for s in rated) / len(rated)
            # Trend: compare last 3 vs prior 3
            if len(rated) >= 4:
                recent_3 = sum(s.progress_rating for s in rated[:3]) / 3
                prior_3 = sum(s.progress_rating for s in rated[3:6]) / min(3, len(rated[3:6]))
                if recent_3 > prior_3 + 0.2:
                    trend = 'up'
                elif recent_3 < prior_3 - 0.2:
                    trend = 'down'

        # Generate initials
        parts = student.name.split()
        initials = (parts[0][0] + (parts[1][0] if len(parts) > 1 else '')).upper()

        # Color based on hash of name
        colors = ['indigo', 'blue', 'purple', 'cyan', 'pink', 'emerald']
        color = colors[hash(student.name) % len(colors)]

        student_pulse.append({
            'student': student,
            'initials': initials,
            'color': color,
            'avg_rating': round(avg_rating, 1) if avg_rating else None,
            'trend': trend,
            'total_sessions': total_count,
            'subject': student.subject or '',
        })

    # ── This month stats ──
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_sessions = Session.query.filter(
        Session.user_id == current_user.id,
        Session.scheduled_at >= month_start,
        Session.status == 'completed',
    ).all()
    month_revenue = sum(s.rate_charged for s in month_sessions)
    month_count = len(month_sessions)

    # Last month for comparison
    if month_start.month == 1:
        last_month_start = month_start.replace(year=month_start.year - 1, month=12)
    else:
        last_month_start = month_start.replace(month=month_start.month - 1)
    last_month_sessions = Session.query.filter(
        Session.user_id == current_user.id,
        Session.scheduled_at >= last_month_start,
        Session.scheduled_at < month_start,
        Session.status == 'completed',
    ).all()
    last_month_revenue = sum(s.rate_charged for s in last_month_sessions)

    # Percent change
    if last_month_revenue > 0:
        revenue_change = round(((month_revenue - last_month_revenue) / last_month_revenue) * 100)
    else:
        revenue_change = 100 if month_revenue > 0 else 0

    # Monthly goal: hourly_rate * 20 sessions as reasonable target
    monthly_goal = (current_user.hourly_rate or 50) * 20
    goal_pct = min(round((month_revenue / monthly_goal) * 100), 100) if monthly_goal > 0 else 0

    return render_template('dashboard/index.html',
        greeting=greeting,
        first_name=first_name,
        current_time=now,
        # Today
        todays_sessions=todays_sessions,
        today_count=len(todays_sessions),
        today_expected=today_expected,
        # Next up
        next_session=next_session,
        prev_session_with_student=prev_session_with_student,
        later_today=later_today,
        # Week
        week_days=week_days,
        # Attention
        attention_items=attention_items,
        # Student pulse
        student_pulse=student_pulse,
        total_students=len(active_students),
        # Month
        month_revenue=month_revenue,
        month_count=month_count,
        revenue_change=revenue_change,
        monthly_goal=monthly_goal,
        goal_pct=goal_pct,
    )
