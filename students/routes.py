from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from database.db import db
from database.models import Student, Session

students_bp = Blueprint('students', __name__, url_prefix='/students')


@students_bp.route('/')
@login_required
def list_students():
    students = Student.query.filter_by(
        user_id=current_user.id, is_active=True
    ).order_by(Student.name).all()
    return render_template('students/list.html', students=students)


@students_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_student():
    if request.method == 'POST':
        student = Student(
            user_id=current_user.id,
            name=request.form.get('name', '').strip(),
            parent_name=request.form.get('parent_name', '').strip(),
            parent_email=request.form.get('parent_email', '').strip(),
            parent_phone=request.form.get('parent_phone', '').strip(),
            grade_level=request.form.get('grade_level', '').strip(),
            subject=request.form.get('subject', '').strip(),
            notes=request.form.get('notes', '').strip(),
        )
        if not student.name:
            flash('Student name is required.', 'error')
            return render_template('students/form.html', student=None, action='Add')

        db.session.add(student)
        db.session.commit()
        flash(f'{student.name} added!', 'success')
        return redirect(url_for('students.list_students'))

    return render_template('students/form.html', student=None, action='Add')


@students_bp.route('/<int:student_id>')
@login_required
def detail(student_id):
    student = Student.query.filter_by(id=student_id, user_id=current_user.id).first_or_404()
    sessions = Session.query.filter_by(
        student_id=student.id
    ).order_by(Session.scheduled_at.desc()).all()
    return render_template('students/detail.html', student=student, sessions=sessions)


@students_bp.route('/<int:student_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_student(student_id):
    student = Student.query.filter_by(id=student_id, user_id=current_user.id).first_or_404()

    if request.method == 'POST':
        student.name = request.form.get('name', '').strip()
        student.parent_name = request.form.get('parent_name', '').strip()
        student.parent_email = request.form.get('parent_email', '').strip()
        student.parent_phone = request.form.get('parent_phone', '').strip()
        student.grade_level = request.form.get('grade_level', '').strip()
        student.subject = request.form.get('subject', '').strip()
        student.notes = request.form.get('notes', '').strip()

        if not student.name:
            flash('Student name is required.', 'error')
            return render_template('students/form.html', student=student, action='Edit')

        db.session.commit()
        flash(f'{student.name} updated!', 'success')
        return redirect(url_for('students.detail', student_id=student.id))

    return render_template('students/form.html', student=student, action='Edit')


@students_bp.route('/<int:student_id>/delete', methods=['POST'])
@login_required
def delete_student(student_id):
    student = Student.query.filter_by(id=student_id, user_id=current_user.id).first_or_404()
    student.is_active = False
    db.session.commit()
    flash(f'{student.name} removed.', 'success')
    return redirect(url_for('students.list_students'))
