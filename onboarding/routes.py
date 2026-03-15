import re
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from database.db import db
from database.models import Availability
from scheduling.utils import DAY_NAMES, save_availability_from_form

onboarding_bp = Blueprint('onboarding', __name__, url_prefix='/onboarding')

TOTAL_STEPS = 5


def slugify(text):
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    return text


@onboarding_bp.route('', methods=['GET', 'POST'])
@login_required
def wizard():
    # If onboarding is already completed, go to dashboard
    if current_user.onboarding_completed:
        return redirect(url_for('dashboard.index'))

    # Get current step from query param or DB
    step = request.args.get('step', type=int)
    if step is None:
        step = current_user.onboarding_step or 1

    # Clamp step to valid range
    step = max(1, min(step, TOTAL_STEPS))

    if request.method == 'POST':
        action = request.form.get('action', 'next')

        if action == 'skip':
            flash('You can always fill this in later from your profile.', 'info')
        else:
            # Process form data based on current step
            if step == 1:
                _save_step1(request.form)
            elif step == 2:
                _save_step2(request.form)
            elif step == 3:
                _save_step3(request.form)
            elif step == 4:
                _save_step4(request.form)
            elif step == 5:
                # Final step - mark onboarding as completed
                current_user.onboarding_completed = True
                current_user.onboarding_step = TOTAL_STEPS
                db.session.commit()
                flash('You are all set! Welcome to TutorHub.', 'success')
                return redirect(url_for('dashboard.index'))

        # Advance to next step
        if step < TOTAL_STEPS:
            next_step = step + 1
            current_user.onboarding_step = next_step
            db.session.commit()
            return redirect(url_for('onboarding.wizard', step=next_step))
        else:
            # Step 5 skip case
            current_user.onboarding_completed = True
            current_user.onboarding_step = TOTAL_STEPS
            db.session.commit()
            flash('You are all set! Welcome to TutorHub.', 'success')
            return redirect(url_for('dashboard.index'))

    # Build context for the template
    context = {
        'step': step,
        'total_steps': TOTAL_STEPS,
    }

    # Add step-specific context
    if step == 4:
        current_avail = Availability.query.filter_by(
            user_id=current_user.id, is_active=True
        ).all()
        avail_dict = {}
        for a in current_avail:
            avail_dict[a.day_of_week] = {
                'enabled': True,
                'start': a.start_time.strftime('%H:%M'),
                'end': a.end_time.strftime('%H:%M'),
            }
        context['day_names'] = DAY_NAMES
        context['avail_dict'] = avail_dict

    if step == 5:
        # Build completeness checklist
        checklist = []
        checklist.append({
            'label': 'Bio',
            'done': bool(current_user.bio and current_user.bio.strip()),
        })
        checklist.append({
            'label': 'Subjects',
            'done': bool(current_user.subjects and current_user.subjects.strip()),
        })
        checklist.append({
            'label': 'Hourly Rate',
            'done': current_user.hourly_rate > 0,
        })
        checklist.append({
            'label': 'Session Durations',
            'done': bool(current_user.session_durations and current_user.session_durations.strip()),
        })
        checklist.append({
            'label': 'Meeting Link',
            'done': bool(current_user.default_meeting_link and current_user.default_meeting_link.strip()),
        })
        avail_count = Availability.query.filter_by(
            user_id=current_user.id, is_active=True
        ).count()
        checklist.append({
            'label': 'Availability',
            'done': avail_count > 0,
        })
        context['checklist'] = checklist
        context['completed_count'] = sum(1 for c in checklist if c['done'])
        context['booking_url'] = url_for('booking.public_profile',
                                         slug=current_user.profile_slug, _external=True)

    return render_template('onboarding/wizard.html', **context)


def _save_step1(form_data):
    """Save bio and profile slug."""
    bio = form_data.get('bio', '').strip()
    if bio:
        current_user.bio = bio

    new_slug = form_data.get('profile_slug', '').strip()
    if new_slug and new_slug != current_user.profile_slug:
        new_slug = slugify(new_slug)
        from database.models import User
        existing = User.query.filter_by(profile_slug=new_slug).first()
        if existing and existing.id != current_user.id:
            flash('That profile URL is already taken. We kept your current one.', 'error')
        else:
            current_user.profile_slug = new_slug

    db.session.commit()


def _save_step2(form_data):
    """Save teaching info: subjects, rate, currency."""
    subjects = form_data.get('subjects', '').strip()
    if subjects:
        current_user.subjects = subjects

    rate = form_data.get('hourly_rate', '')
    if rate:
        try:
            current_user.hourly_rate = float(rate)
        except ValueError:
            pass

    currency = form_data.get('currency', '').strip()
    if currency:
        current_user.currency = currency

    db.session.commit()


def _save_step3(form_data):
    """Save session setup: durations, meeting link, timezone, phone, address."""
    # Session durations from checkbox pills
    durations = form_data.getlist('session_durations')
    if durations:
        current_user.session_durations = ','.join(durations)

    meeting_link = form_data.get('default_meeting_link', '').strip()
    if meeting_link:
        current_user.default_meeting_link = meeting_link

    timezone = form_data.get('timezone', '').strip()
    if timezone:
        current_user.timezone = timezone

    phone = form_data.get('phone', '').strip()
    current_user.phone = phone

    address = form_data.get('address', '').strip()
    current_user.address = address

    db.session.commit()


def _save_step4(form_data):
    """Save availability using shared utility."""
    save_availability_from_form(current_user.id, form_data)
