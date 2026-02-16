"""
Email notification service for TutorHub.
Uses Gmail SMTP to send booking confirmations to tutors and students.
Runs asynchronously so email failures never block the booking flow.
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from threading import Thread


def send_booking_confirmation_async(tutor_email, tutor_name, student_name,
                                     student_email, session_datetime,
                                     duration_minutes, session_type,
                                     subject='', meeting_link=None):
    """Send booking confirmation emails in a background thread."""
    thread = Thread(
        target=_send_booking_emails,
        args=(tutor_email, tutor_name, student_name, student_email,
              session_datetime, duration_minutes, session_type,
              subject, meeting_link),
        daemon=True
    )
    thread.start()


def _send_booking_emails(tutor_email, tutor_name, student_name, student_email,
                          session_datetime, duration_minutes, session_type,
                          subject, meeting_link):
    """Send both tutor and student notification emails."""
    try:
        formatted_date = session_datetime.strftime('%A, %B %d, %Y')
        formatted_time = session_datetime.strftime('%I:%M %p')
        type_label = 'Online' if session_type == 'online' else 'In-Person'

        # --- Tutor notification ---
        tutor_subject = f'New Booking: {student_name} on {formatted_date}'
        tutor_html = f"""
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <div style="background: #4F46E5; color: white; padding: 24px; border-radius: 8px 8px 0 0;">
        <h1 style="margin: 0; font-size: 22px;">New Session Booked!</h1>
    </div>
    <div style="background: #ffffff; padding: 24px; border: 1px solid #E5E7EB; border-top: none; border-radius: 0 0 8px 8px;">
        <p style="color: #374151; font-size: 16px;">Hi {tutor_name},</p>
        <p style="color: #374151;">A new tutoring session has been booked:</p>
        <table style="width: 100%; border-collapse: collapse; margin: 16px 0;">
            <tr><td style="padding: 8px 0; color: #6B7280; width: 140px;">Student</td><td style="padding: 8px 0; color: #111827; font-weight: 600;">{student_name}</td></tr>
            <tr><td style="padding: 8px 0; color: #6B7280;">Email</td><td style="padding: 8px 0; color: #111827;">{student_email}</td></tr>
            <tr><td style="padding: 8px 0; color: #6B7280;">Date</td><td style="padding: 8px 0; color: #111827; font-weight: 600;">{formatted_date}</td></tr>
            <tr><td style="padding: 8px 0; color: #6B7280;">Time</td><td style="padding: 8px 0; color: #111827; font-weight: 600;">{formatted_time}</td></tr>
            <tr><td style="padding: 8px 0; color: #6B7280;">Duration</td><td style="padding: 8px 0; color: #111827;">{duration_minutes} minutes</td></tr>
            <tr><td style="padding: 8px 0; color: #6B7280;">Type</td><td style="padding: 8px 0; color: #111827;">{type_label}</td></tr>
            {'<tr><td style="padding: 8px 0; color: #6B7280;">Subject</td><td style="padding: 8px 0; color: #111827;">' + subject + '</td></tr>' if subject else ''}
        </table>
        <p style="color: #6B7280; font-size: 14px;">Check your TutorHub dashboard for full details.</p>
    </div>
</div>
"""
        _send_email(tutor_email, tutor_subject, tutor_html)

        # --- Student confirmation ---
        student_subject_line = f'Session Confirmed with {tutor_name}'
        meeting_section = ''
        if session_type == 'online' and meeting_link:
            meeting_section = f"""
        <div style="background: #EEF2FF; border: 1px solid #C7D2FE; border-radius: 8px; padding: 16px; margin: 16px 0;">
            <p style="color: #4F46E5; font-weight: 600; margin: 0 0 8px 0;">Meeting Link</p>
            <a href="{meeting_link}" style="color: #4F46E5; word-break: break-all;">{meeting_link}</a>
            <p style="color: #6B7280; font-size: 13px; margin: 8px 0 0 0;">Please join 5 minutes before your session starts.</p>
        </div>
"""

        student_html = f"""
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <div style="background: #4F46E5; color: white; padding: 24px; border-radius: 8px 8px 0 0;">
        <h1 style="margin: 0; font-size: 22px;">Session Confirmed!</h1>
    </div>
    <div style="background: #ffffff; padding: 24px; border: 1px solid #E5E7EB; border-top: none; border-radius: 0 0 8px 8px;">
        <p style="color: #374151; font-size: 16px;">Hi {student_name},</p>
        <p style="color: #374151;">Your tutoring session with <strong>{tutor_name}</strong> is confirmed:</p>
        <table style="width: 100%; border-collapse: collapse; margin: 16px 0;">
            <tr><td style="padding: 8px 0; color: #6B7280; width: 140px;">Date</td><td style="padding: 8px 0; color: #111827; font-weight: 600;">{formatted_date}</td></tr>
            <tr><td style="padding: 8px 0; color: #6B7280;">Time</td><td style="padding: 8px 0; color: #111827; font-weight: 600;">{formatted_time}</td></tr>
            <tr><td style="padding: 8px 0; color: #6B7280;">Duration</td><td style="padding: 8px 0; color: #111827;">{duration_minutes} minutes</td></tr>
            <tr><td style="padding: 8px 0; color: #6B7280;">Type</td><td style="padding: 8px 0; color: #111827;">{type_label}</td></tr>
            {'<tr><td style="padding: 8px 0; color: #6B7280;">Subject</td><td style="padding: 8px 0; color: #111827;">' + subject + '</td></tr>' if subject else ''}
        </table>
        {meeting_section}
        <p style="color: #6B7280; font-size: 14px;">If you need to reschedule, please contact {tutor_name} directly.</p>
    </div>
</div>
"""
        _send_email(student_email, student_subject_line, student_html)

    except Exception as e:
        # Log but never crash â booking already succeeded
        print(f'[TutorHub Email] Error sending notifications: {e}')


def _send_email(to_email, subject, html_body):
    """Send a single HTML email via Gmail SMTP."""
    username = os.getenv('MAIL_USERNAME', '')
    password = os.getenv('MAIL_PASSWORD', '')

    if not username or not password:
        return  # Email not configured â skip silently

    msg = MIMEMultipart('alternative')
    msg['From'] = f'TutorHub <{username}>'
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(html_body, 'html'))

    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.starttls()
        server.login(username, password)
        server.send_message(msg)
