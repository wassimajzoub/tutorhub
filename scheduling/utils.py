from datetime import datetime, timedelta, time, date
from database.models import Availability, Session


DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']


def get_available_slots(tutor_id, target_date, duration_minutes=60):
    """
    Generate available time slots for a tutor on a given date.
    Returns a list of datetime objects representing slot start times.
    """
    day_of_week = target_date.weekday()  # 0=Mon, 6=Sun

    # Get tutor's availability for this day of week
    availabilities = Availability.query.filter_by(
        user_id=tutor_id,
        day_of_week=day_of_week,
        is_active=True,
    ).all()

    if not availabilities:
        return []

    # Get existing sessions on this date
    day_start = datetime.combine(target_date, time(0, 0))
    day_end = day_start + timedelta(days=1)

    booked_sessions = Session.query.filter(
        Session.user_id == tutor_id,
        Session.scheduled_at >= day_start,
        Session.scheduled_at < day_end,
        Session.status != 'cancelled',
    ).all()

    # Build list of booked time ranges
    booked_ranges = []
    for s in booked_sessions:
        booked_start = s.scheduled_at
        booked_end = booked_start + timedelta(minutes=s.duration_minutes)
        booked_ranges.append((booked_start, booked_end))

    # Generate slots from availability windows
    slots = []
    for avail in availabilities:
        slot_start = datetime.combine(target_date, avail.start_time)
        window_end = datetime.combine(target_date, avail.end_time)

        while slot_start + timedelta(minutes=duration_minutes) <= window_end:
            slot_end = slot_start + timedelta(minutes=duration_minutes)

            # Check if this slot overlaps any booked session
            is_available = True
            for booked_start, booked_end in booked_ranges:
                if slot_start < booked_end and slot_end > booked_start:
                    is_available = False
                    break

            if is_available:
                slots.append(slot_start)

            slot_start += timedelta(minutes=30)  # 30-min increments

    slots.sort()
    return slots


def format_availability(availabilities):
    """Format availability records into a readable string."""
    by_day = {}
    for avail in availabilities:
        day = DAY_NAMES[avail.day_of_week]
        time_str = f"{avail.start_time.strftime('%I:%M %p')} - {avail.end_time.strftime('%I:%M %p')}"
        by_day.setdefault(day, []).append(time_str)

    parts = []
    for day in DAY_NAMES:
        if day in by_day:
            times = ', '.join(by_day[day])
            parts.append(f"{day}: {times}")
    return parts
