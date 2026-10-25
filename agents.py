"""Agent profiles — load students, extract free slots from schedules."""

import json
import os
import re

PROFILES_PATH = os.path.join(os.path.dirname(__file__), "profiles", "students.json")

# ponytail: global load, reload with load_profiles() if needed
_profiles = {}


def load_profiles(path=None):
    global _profiles
    with open(path or PROFILES_PATH) as f:
        _profiles = json.load(f)
    return _profiles


def get_profiles():
    if not _profiles:
        load_profiles()
    return _profiles


def get_profile(student_id):
    return get_profiles()[student_id]


def all_student_ids():
    return list(get_profiles().keys())


# --- Schedule utilities ---

# Day blocks: 8am-10pm in 30-min slots
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]
SLOT_START = 8 * 60   # 8:00
SLOT_END = 22 * 60    # 22:00
SLOT_STEP = 30


def _parse_time(t):
    """Parse 'H:MM' or 'HH:MM' to minutes since midnight."""
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def _parse_schedule_entry(entry):
    """Parse '9:00-10:15 CSE310' → (start_min, end_min)."""
    match = re.match(r"(\d+:\d+)-(\d+:\d+)", entry)
    if not match:
        return None
    return _parse_time(match.group(1)), _parse_time(match.group(2))


def _all_slots(day):
    """All 30-min slot labels for a day: 'Mon 8:00-8:30', etc."""
    slots = []
    t = SLOT_START
    while t + SLOT_STEP <= SLOT_END:
        h1, m1 = divmod(t, 60)
        h2, m2 = divmod(t + SLOT_STEP, 60)
        slots.append(f"{day} {h1}:{m1:02d}-{h2}:{m2:02d}")
        t += SLOT_STEP
    return slots


def get_free_slots(student_id):
    """Extract free 30-min slots from a student's schedule."""
    profile = get_profile(student_id)
    schedule = profile.get("schedule", {})
    free = []

    for day in DAYS:
        busy_ranges = []
        for entry in schedule.get(day, []):
            parsed = _parse_schedule_entry(entry)
            if parsed:
                busy_ranges.append(parsed)

        for slot_label in _all_slots(day):
            match = re.match(r"\w+ (\d+:\d+)-(\d+:\d+)", slot_label)
            slot_start = _parse_time(match.group(1))
            slot_end = _parse_time(match.group(2))

            conflict = any(
                slot_start < end and slot_end > start
                for start, end in busy_ranges
            )
            if not conflict:
                free.append(slot_label)

    return free


def get_free_slots_hourly(student_id):
    """Get free 1-hour blocks (more readable for proposals)."""
    profile = get_profile(student_id)
    schedule = profile.get("schedule", {})
    free = []

    for day in DAYS:
        busy_ranges = []
        for entry in schedule.get(day, []):
            parsed = _parse_schedule_entry(entry)
            if parsed:
                busy_ranges.append(parsed)

        t = SLOT_START
        while t + 60 <= SLOT_END:
            conflict = any(
                t < end and (t + 60) > start
                for start, end in busy_ranges
            )
            if not conflict:
                h1, m1 = divmod(t, 60)
                h2, m2 = divmod(t + 60, 60)
                free.append(f"{day} {h1}:{m1:02d}-{h2}:{m2:02d}")
            t += 60

    return free


def has_schedule_conflict(student_id, day, start_str, end_str):
    """Check if a student has a conflict on day between start-end times."""
    profile = get_profile(student_id)
    schedule = profile.get("schedule", {})
    start = _parse_time(start_str)
    end = _parse_time(end_str)

    for entry in schedule.get(day, []):
        parsed = _parse_schedule_entry(entry)
        if parsed and start < parsed[1] and end > parsed[0]:
            return True
    return False


def get_courses(student_id):
    """Get course list for a student."""
    return get_profile(student_id).get("courses", [])


def students_in_course(subject, number):
    """Find all students enrolled in a course."""
    result = []
    for sid, profile in get_profiles().items():
        for c in profile.get("courses", []):
            if c["subject"] == subject.upper() and c["number"] == str(number):
                result.append(sid)
                break
    return result


if __name__ == "__main__":
    load_profiles()
    for sid in all_student_ids():
        slots = get_free_slots_hourly(sid)
        print(f"{sid}: {len(slots)} free hour blocks")
        print(f"  First 5: {slots[:5]}")
    print(f"\nStudents in CSE 310: {students_in_course('CSE', '310')}")
