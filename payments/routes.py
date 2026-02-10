from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from database.db import db
from database.models import Session, Student, Invoice

payments_bp = Blueprint('payments', __name__, url_prefix='/payments')


@payments_bp.route('/')
@login_required
def overview():
    # Unpaid completed sessions
    unpaid = Session.query.filter(
        Session.user_id == current_user.id,
        Session.status == 'completed',
        Session.is_paid == False,
    ).order_by(Session.scheduled_at.desc()).all()

    # Recent paid sessions
    recent_paid = Session.query.filter(
        Session.user_id == current_user.id,
        Session.is_paid == True,
    ).order_by(Session.paid_date.desc()).limit(20).all()

    # Per-student outstanding
    students = Student.query.filter_by(user_id=current_user.id, is_active=True).all()
    student_balances = []
    for s in students:
        owed = Session.query.filter(
            Session.student_id == s.id,
            Session.status == 'completed',
            Session.is_paid == False,
        ).all()
        if owed:
            student_balances.append({
                'student': s,
                'sessions': owed,
                'total': sum(sess.rate_charged for sess in owed),
            })

    return render_template('payments/overview.html',
        unpaid=unpaid,
        recent_paid=recent_paid,
        student_balances=student_balances,
    )


@payments_bp.route('/invoice/generate', methods=['POST'])
@login_required
def generate_invoice():
    session_ids = request.form.getlist('session_ids')
    if not session_ids:
        flash('Select at least one session.', 'error')
        return redirect(url_for('payments.overview'))

    sessions = Session.query.filter(
        Session.id.in_([int(sid) for sid in session_ids]),
        Session.user_id == current_user.id,
    ).all()

    if not sessions:
        flash('No valid sessions found.', 'error')
        return redirect(url_for('payments.overview'))

    total = sum(s.rate_charged for s in sessions)

    # Generate invoice number
    count = Invoice.query.filter_by(user_id=current_user.id).count()
    now = datetime.utcnow()
    inv_number = f"INV-{now.year}-{now.month:02d}-{count + 1:03d}"

    student_id = sessions[0].student_id

    invoice = Invoice(
        user_id=current_user.id,
        student_id=student_id,
        invoice_number=inv_number,
        session_ids=','.join(str(s.id) for s in sessions),
        total_amount=total,
        generated_date=now,
    )
    db.session.add(invoice)
    db.session.commit()

    return redirect(url_for('payments.view_invoice', invoice_id=invoice.id))


@payments_bp.route('/invoice/<int:invoice_id>')
@login_required
def view_invoice(invoice_id):
    invoice = Invoice.query.filter_by(id=invoice_id, user_id=current_user.id).first_or_404()
    session_id_list = [int(sid) for sid in invoice.session_ids.split(',') if sid]
    sessions = Session.query.filter(Session.id.in_(session_id_list)).all()
    student = Student.query.get(invoice.student_id) if invoice.student_id else None

    return render_template('payments/invoice.html',
        invoice=invoice,
        sessions=sessions,
        student=student,
        tutor=current_user,
    )
