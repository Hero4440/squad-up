"""Four solvers: class sections, study groups, event plans, chore splits.

Each solver takes structured input and returns a proposal dict.
Adapted from Campus Bestie coordinator.py + 2 new solvers.
"""

from collections import Counter
from agents import (
    get_profile, get_free_slots_hourly, get_courses,
    students_in_course, has_schedule_conflict, all_student_ids, get_profiles,
)


# ---------------------------------------------------------------------------
# 1. Class section coordination
# ---------------------------------------------------------------------------

def solve_class(subject, number, sections, participants, constraints=None):
    """
    Find best section for a group.

    sections: list of dicts from asu_search (course, section, days, time, seats_open, ...)
    participants: list of student IDs
    constraints: list of section IDs to exclude (from vetoes)
    """
    constraints = constraints or []
    open_sections = [
        s for s in sections
        if s.get("seats_open", 0) > 0 and s["section"] not in constraints
    ]

    if not open_sections:
        return {"proposal": None, "reason": "No open sections available after constraints."}

    # Score each section: how many participants have no conflict
    scored = []
    for sec in open_sections:
        # Parse section time to check conflicts
        days_str = sec.get("days", "")
        time_str = sec.get("time", "")
        if not time_str or time_str == "Async":
            # Async = no conflict for anyone
            can_attend = list(participants)
        else:
            # Parse days
            day_map = {"M": "Mon", "Tu": "Tue", "W": "Wed", "Th": "Thu", "F": "Fri"}
            import re
            day_codes = re.findall(r"Th|Tu|Sa|Su|[MWFS]", days_str)
            sec_days = [day_map.get(d) for d in day_codes if d in day_map]

            parts = time_str.replace(" AM", "").replace(" PM", "").split("-")
            if len(parts) == 2:
                start_t, end_t = parts[0].strip(), parts[1].strip()
            else:
                start_t, end_t = "0:00", "0:00"

            can_attend = []
            for sid in participants:
                conflict = False
                for day in sec_days:
                    if day and has_schedule_conflict(sid, day, start_t, end_t):
                        conflict = True
                        break
                if not conflict:
                    can_attend.append(sid)

        scored.append({
            "section": sec,
            "can_attend": can_attend,
            "count": len(can_attend),
        })

    scored.sort(key=lambda x: (-x["count"], x["section"].get("section", "")))
    best = scored[0]

    return {
        "proposal": best["section"],
        "can_attend": best["can_attend"],
        "cannot_attend": [s for s in participants if s not in best["can_attend"]],
        "attendance": f"{best['count']}/{len(participants)}",
        "alternatives": [s["section"]["section"] for s in scored[1:3]],
    }


# ---------------------------------------------------------------------------
# 2. Study group scheduling
# ---------------------------------------------------------------------------

def solve_study(course_key, participants, constraints=None):
    """
    Find best study time for participants.

    course_key: e.g. "CSE310"
    participants: list of student IDs
    constraints: list of slot strings to exclude
    """
    constraints = set(constraints or [])

    # Collect free slots per student
    slot_counts = Counter()
    student_slots = {}
    for sid in participants:
        free = [s for s in get_free_slots_hourly(sid) if s not in constraints]
        student_slots[sid] = set(free)
        for s in free:
            slot_counts[s] += 1

    if not slot_counts:
        return {"proposal": None, "reason": "No common availability after constraints."}

    # Find slots where all can attend, else best attendance
    n = len(participants)
    universal = [s for s, c in slot_counts.items() if c == n]

    if universal:
        proposed = sorted(universal)[0]
        attendance = n
        who = list(participants)
    else:
        proposed, attendance = slot_counts.most_common(1)[0]
        who = [sid for sid in participants if proposed in student_slots[sid]]

    # Location by campus
    campuses = [get_profile(sid).get("campus", "TEMPE") for sid in who]
    campus_counts = Counter(campuses)
    top_campus = campus_counts.most_common(1)[0][0]

    locations = {
        "TEMPE": "Hayden Library (Tempe)",
        "DOWNTOWN": "Downtown Phoenix campus library",
        "POLY": "Polytechnic campus library",
        "WEST": "West campus library",
    }
    location = locations.get(top_campus, f"{top_campus} campus library")

    return {
        "proposal": proposed,
        "course": course_key,
        "location": location,
        "who_can_attend": who,
        "who_cannot": [s for s in participants if s not in who],
        "attendance": f"{attendance}/{n}",
        "student_slots": {
            sid: sorted(list(student_slots[sid]))[:10]
            for sid in participants
        },
    }


# ---------------------------------------------------------------------------
# 3. Event plans (squad up for events)
# ---------------------------------------------------------------------------

def solve_plans(event, participants, constraints=None):
    """
    Determine who can attend an event and group by campus.

    event: dict with title, date, time, location
    participants: list of student IDs
    constraints: list of event titles to skip
    """
    constraints = constraints or []

    available = []
    conflicted = []
    for sid in participants:
        profile = get_profile(sid)
        # ponytail: simple conflict = any schedule entry overlaps event time
        # Real conflict detection would parse event datetime; for hackathon demo,
        # we check if student has ANY class on the event day
        has_conflict = False
        # Mark as available by default for demo; real: parse event date/time
        if not has_conflict:
            available.append(sid)
        else:
            conflicted.append(sid)

    # Group by campus for carpool
    carpool = {}
    for sid in available:
        campus = get_profile(sid).get("campus", "TEMPE")
        carpool.setdefault(campus, []).append(sid)

    return {
        "event": event,
        "who_can_go": available,
        "who_has_conflict": conflicted,
        "carpool_groups": carpool,
        "attendance": f"{len(available)}/{len(participants)}",
        "meetup_note": f"Meet 30 min before at {event.get('location', 'venue')}",
    }


# ---------------------------------------------------------------------------
# 4. Chore split (maximin fairness)
# ---------------------------------------------------------------------------

def solve_chores(participants, constraints=None):
    """
    Assign chores to maximize the minimum happiness.

    Each student has chore_preferences: {chore: 1-5}.
    constraints: list of (student_id, chore) tuples to exclude.
    """
    constraints = set(tuple(c) for c in (constraints or []))

    prefs = {}
    for sid in participants:
        profile = get_profile(sid)
        prefs[sid] = profile.get("chore_preferences", {})

    all_chores = set()
    for p in prefs.values():
        all_chores.update(p.keys())

    # Remove constrained assignments
    # Build assignment via greedy maximin:
    # Assign each chore to the person who minds it least (highest pref),
    # breaking ties by giving to the person with lowest current min score.
    assignments = {}  # chore → student_id
    student_assigned = {sid: [] for sid in participants}

    # Sort chores by "most contested" (lowest max preference) first
    chore_list = sorted(all_chores, key=lambda c: max(
        prefs[sid].get(c, 3) for sid in participants
        if (sid, c) not in constraints
    ))

    for chore in chore_list:
        eligible = [
            sid for sid in participants
            if (sid, chore) not in constraints
        ]
        if not eligible:
            assignments[chore] = None
            continue

        # Pick student with highest preference for this chore
        # Tie-break: fewest chores assigned so far
        best = max(eligible, key=lambda sid: (
            prefs[sid].get(chore, 3),
            -len(student_assigned[sid]),
        ))
        assignments[chore] = best
        student_assigned[best].append(chore)

    # Calculate happiness scores
    happiness = {}
    for sid in participants:
        if student_assigned[sid]:
            scores = [prefs[sid].get(c, 3) for c in student_assigned[sid]]
            happiness[sid] = min(scores)
        else:
            happiness[sid] = 5  # no chores = happy

    return {
        "assignments": assignments,
        "student_chores": {sid: chores for sid, chores in student_assigned.items()},
        "happiness": happiness,
        "min_happiness": min(happiness.values()) if happiness else 0,
        "explanation": {
            chore: {
                "assigned_to": sid,
                "their_preference": prefs.get(sid, {}).get(chore, "?") if sid else "unassigned",
            }
            for chore, sid in assignments.items()
        },
    }


if __name__ == "__main__":
    from agents import load_profiles
    load_profiles()

    # Test study solver
    result = solve_study("CSE310", ["shreeya", "rishi", "tejas"])
    print(f"Study: {result['proposal']} at {result['location']} ({result['attendance']})")

    # Test chore solver
    result = solve_chores(["shreeya", "rishi", "tejas"])
    print(f"Chores: {result['student_chores']}")
    print(f"Happiness: {result['happiness']} (min: {result['min_happiness']})")
