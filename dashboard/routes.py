from datetime import datetime, timedelta
from flask import Blueprint, render_template
from flask_login import login_required, current_user
from database.models import Session, Student

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/dashboard')
@login_required
def index():
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    week_end = today_start + timedelta(days=7)

    todays_sessions = Session.query.filter(
        Session.user_id == current_user.id,
        Session.scheduled_at >= today_start,
        Session.scheduled_at < today_end,
        Session.status != 'cancelled',
    ).order_by(Session.scheduled_at).all()

    upcoming_sessions = Session.query.filter(
        Session.user_id == current_user.id,
        Session.scheduled_at >= today_end,
        Session.scheduled_at < week_end,
        Session.status != 'cancelled',
    ).order_by(Session.scheduled_at).all()

    total_students = Student.query.filter_by(user_id=current_user.id, is_active=True).count()

    # This month stats
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_sessions = Session.query.filter(
        Session.user_id == current_user.id,
        Session.scheduled_at >= month_start,
        Session.status == 'completed',
    ).all()

    month_revenue = sum(s.rate_charged for s in month_sessions)
    month_count = len(month_sessions)

    unpaid_sessions = Session.query.filter(
        Session.user_id == current_user.id,
        Session.status == 'completed',
        Session.is_paid == False,
    ).all()
    outstanding = sum(s.rate_charged for s in unpaid_sessions)

    return render_template('dashboard/index.html',
        todays_sessions=todays_sessions,
        upcoming_sessions=upcoming_sessions,
        total_students=total_students,
        month_revenue=month_revenue,
        month_count=month_count,
        outstanding=outstanding,
        unpaid_count=len(unpaid_sessions),
    )
