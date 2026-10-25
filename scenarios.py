"""RoomieAgent — scripted 13-step roommate matching scenario engine.

Each user walks through the same flow independently.
State is in-memory; server restart = fresh demo.
"""

import random

# --- Preference questions (steps 3-7) ---
ROOMMATE_QUESTIONS = [
    {
        "key": "sleep",
        "title": "Sleep schedule",
        "subtitle": "When do you usually sleep?",
        "options": ["Early bird (10pm-6am)", "Normal (11pm-7am)", "Night owl (1am-9am)"],
    },
    {
        "key": "diet",
        "title": "Kitchen & diet",
        "subtitle": "Any food preferences?",
        "options": ["No restrictions", "Vegetarian", "Vegan", "Halal"],
    },
    {
        "key": "budget",
        "title": "Monthly budget",
        "subtitle": "What's your range for rent + utilities?",
        "options": ["$500-700", "$700-900", "$900-1100", "$1100+"],
    },
    {
        "key": "smoking",
        "title": "Smoking & vaping",
        "subtitle": "Your preference?",
        "options": ["No smoking/vaping", "Outside only", "No preference"],
    },
    {
        "key": "room",
        "title": "Room setup",
        "subtitle": "How do you keep your space?",
        "options": ["Very neat", "Mostly tidy", "Organized chaos", "Whatever works"],
    },
]

# --- Scripted matches ---
# Each user gets matched with exactly one partner. 4/5 compat for demo.
MATCHES = {
    "shreeya": {
        "partner": "arjun",
        "score": 4, "of": 5,
        "alignment": [
            {"label": "Sleep schedule", "match": True, "detail": "Both early birds"},
            {"label": "Budget range", "match": True, "detail": "$700-900"},
            {"label": "Room tidiness", "match": True, "detail": "Both very neat"},
            {"label": "Kitchen", "match": False, "detail": "Different diet prefs"},
            {"label": "No smoking", "match": True, "detail": "Both non-smokers"},
        ],
        "flags": [],
    },
    "arjun": {
        "partner": "shreeya",
        "score": 4, "of": 5,
        "alignment": [
            {"label": "Sleep schedule", "match": True, "detail": "Both early birds"},
            {"label": "Budget range", "match": True, "detail": "$700-900"},
            {"label": "Room tidiness", "match": True, "detail": "Both very neat"},
            {"label": "Kitchen", "match": False, "detail": "Different diet prefs"},
            {"label": "No smoking", "match": True, "detail": "Both non-smokers"},
        ],
        "flags": [],
    },
    "rishi": {
        "partner": "tejas",
        "score": 4, "of": 5,
        "alignment": [
            {"label": "Sleep schedule", "match": True, "detail": "Both night owls"},
            {"label": "Budget range", "match": True, "detail": "$500-700"},
            {"label": "Room tidiness", "match": False, "detail": "Different standards"},
            {"label": "Kitchen", "match": True, "detail": "No restrictions"},
            {"label": "No smoking", "match": True, "detail": "Both non-smokers"},
        ],
        "flags": [],
    },
    "tejas": {
        "partner": "rishi",
        "score": 4, "of": 5,
        "alignment": [
            {"label": "Sleep schedule", "match": True, "detail": "Both night owls"},
            {"label": "Budget range", "match": True, "detail": "$500-700"},
            {"label": "Room tidiness", "match": False, "detail": "Different standards"},
            {"label": "Kitchen", "match": True, "detail": "No restrictions"},
            {"label": "No smoking", "match": True, "detail": "Both non-smokers"},
        ],
        "flags": [],
    },
}

# Partner display names (anonymous until reveal)
_PARTNER_NAMES = {
    "shreeya": "Arjun", "arjun": "Shreeya",
    "rishi": "Tejas", "tejas": "Rishi",
}

# Group chat intro messages per user
_GROUP_INTROS = {
    "shreeya": [
        {"type": "bot", "text": "Hey everyone! Looking for Spring 2027 housing near Tempe campus. I'm organized, early bird, love morning study sessions ☀️"},
    ],
    "rishi": [
        {"type": "bot", "text": "Yo! Need a roommate for Spring 2027. Downtown campus, night owl, into hackathons and basketball 🏀"},
    ],
    "tejas": [
        {"type": "bot", "text": "Hey! Chill guy looking for Spring 2027 housing. Tempe campus, flexible schedule, down for whatever 🎮"},
    ],
    "arjun": [
        {"type": "bot", "text": "Hi all! Looking for a roommate near Tempe for Spring 2027. Early riser, keep things neat, into morning runs 🏃"},
    ],
}

# --- Per-user state ---
_state = {}


def _get(user):
    if user not in _state:
        _state[user] = {"step": 0, "prefs": {}, "revealed": False}
    return _state[user]


def _partner_name(user):
    return _PARTNER_NAMES.get(user, "Your match")


def current(user):
    """Return initial state for a user's current step."""
    st = _get(user)
    step = st["step"]

    if step == 0:
        return _step_group_chat(user)
    elif step == 1:
        return _step_transition(user)
    elif step == 2:
        return _step_private_dm(user)
    elif 3 <= step <= 7:
        return _step_preference(user, step - 3)
    elif step == 8:
        return _step_saved(user)
    elif step == 9:
        return _step_match_found(user)
    elif step == 10:
        return _step_match_detail(user)
    elif step == 11:
        return _step_confirmed(user)
    elif step == 12:
        return _step_house_group(user)
    elif step == 13:
        return _step_chores(user)
    else:
        return {"messages": [{"type": "bot", "text": "Demo complete! 🎉"}], "ui_patch": {}}


def advance(user, action, value=None):
    """Advance user to next step based on action. Returns (messages, ui_patch)."""
    st = _get(user)
    step = st["step"]

    # Save preference if in preference steps
    if 3 <= step <= 7 and action == "pick" and value is not None:
        q = ROOMMATE_QUESTIONS[step - 3]
        st["prefs"][q["key"]] = value

    # Match card actions
    if step == 9 and action == "show_more":
        st["revealed"] = True
        st["step"] = 10
        return current(user)
    if step == 9 and action == "connect":
        st["step"] = 11
        return current(user)
    if step == 10 and action == "connect":
        st["step"] = 11
        return current(user)

    # Generic advance
    st["step"] = step + 1
    return current(user)


def _step_group_chat(user):
    """Step 0: Group chat with intros + notice card."""
    msgs = [
        {"type": "system", "text": "ASU Spring 2027 Housing"},
    ]
    # Add other people's intros first, then user's
    for uid in ["shreeya", "rishi", "tejas", "arjun"]:
        if uid != user:
            for m in _GROUP_INTROS.get(uid, []):
                msgs.append({**m, "sender": uid})
    # Notice card for CTA
    msgs.append({
        "type": "notice_card",
        "title": "🏠 RoomieAgent",
        "body": "I can match you with compatible roommates based on your lifestyle, schedule, and preferences. Everything you share stays private until you choose to connect.",
        "cta": "Start Roommate Matching",
        "action": "start",
    })
    return {
        "messages": msgs,
        "ui_patch": {"header_title": "ASU Spring 2027 Housing", "header_subtitle": "Shreeya, Rishi, Tejas, Arjun", "mode": "group"},
    }


def _step_transition(user):
    """Step 1: Transition to private DM."""
    return {
        "messages": [
            {"type": "bot", "text": "I've sent you a private message! Let's find your perfect roommate match 🔒"},
        ],
        "ui_patch": {"header_title": "RoomieAgent", "header_subtitle": "Private chat", "mode": "private"},
    }


def _step_private_dm(user):
    """Step 2: Privacy explanation + consent."""
    return {
        "messages": [
            {"type": "bot", "text": "Hey! This is just between us. I'll ask you 5 quick questions about your lifestyle preferences."},
            {"type": "bot", "text": "Your answers stay private — I only share compatibility scores, never your actual responses."},
            {"type": "notice_card", "title": "🔒 Privacy first", "body": "Your preferences are encrypted and never shared with other users. Only compatibility scores are visible.", "cta": "Yes, let's go!", "action": "consent"},
        ],
        "ui_patch": {"header_title": "RoomieAgent", "header_subtitle": "Private chat", "mode": "private"},
    }


def _step_preference(user, q_index):
    """Steps 3-7: One preference question each."""
    q = ROOMMATE_QUESTIONS[q_index]
    progress = f"Question {q_index + 1} of {len(ROOMMATE_QUESTIONS)}"
    return {
        "messages": [
            {"type": "system", "text": progress},
            {"type": "pref_card", "topic": q["key"], "title": q["title"], "subtitle": q["subtitle"],
             "items": [{"key": opt, "label": opt} for opt in q["options"]]},
        ],
        "ui_patch": {"header_title": "RoomieAgent", "header_subtitle": f"Private chat · {progress}", "mode": "private"},
    }


def _step_saved(user):
    """Step 8: Preferences saved, matching..."""
    return {
        "messages": [
            {"type": "bot", "text": "All saved! Analyzing compatibility with other students... 🔍"},
            {"type": "system", "text": "Matching in progress..."},
        ],
        "ui_patch": {"header_title": "RoomieAgent", "header_subtitle": "Finding your match...", "mode": "private"},
    }


def _step_match_found(user):
    """Step 9: Anonymous match card."""
    match = MATCHES.get(user, MATCHES["shreeya"])
    return {
        "messages": [
            {"type": "bot", "text": "Found a great match for you! 🎉"},
            {
                "type": "match_card",
                "score": match["score"],
                "of": match["of"],
                "alignment": match["alignment"],
                "flags": match["flags"],
                "actions": [
                    {"label": "Show more", "action": "show_more"},
                    {"label": "Connect", "action": "connect"},
                    {"label": "Pass", "action": "pass"},
                ],
                "revealed": False,
                "partner_name": None,
            },
        ],
        "ui_patch": {"header_title": "RoomieAgent", "header_subtitle": "Match found!", "mode": "private"},
    }


def _step_match_detail(user):
    """Step 10: Revealed match detail."""
    match = MATCHES.get(user, MATCHES["shreeya"])
    partner = _partner_name(user)
    return {
        "messages": [
            {"type": "bot", "text": f"Here's more about your match:"},
            {
                "type": "match_card",
                "score": match["score"],
                "of": match["of"],
                "alignment": match["alignment"],
                "flags": match["flags"],
                "actions": [
                    {"label": "Connect", "action": "connect"},
                    {"label": "Pass", "action": "pass"},
                ],
                "revealed": True,
                "partner_name": partner,
            },
        ],
        "ui_patch": {"header_title": "RoomieAgent", "header_subtitle": f"Match: {partner}", "mode": "private"},
    }


def _step_confirmed(user):
    """Step 11: Connection confirmed."""
    partner = _partner_name(user)
    return {
        "messages": [
            {"type": "bot", "text": f"You and {partner} are now connected! 🎉 Setting up your house group chat..."},
            {"type": "system", "text": f"Connected with {partner}"},
        ],
        "ui_patch": {"header_title": "RoomieAgent", "header_subtitle": f"Connected with {partner}", "mode": "private"},
    }


def _step_house_group(user):
    """Step 12: House group chat."""
    partner = _partner_name(user)
    return {
        "messages": [
            {"type": "system", "text": f"Welcome to Our Place 🏠"},
            {"type": "bot", "text": f"Welcome to your new house group! 🏠 You and {partner} can plan everything here."},
            {"type": "bot", "text": "What should we tackle first?"},
            {
                "type": "notice_card",
                "title": "🏠 House setup",
                "body": "Let's get your place organized! Pick something to start with.",
                "cta": "Split chores",
                "action": "chores",
            },
        ],
        "ui_patch": {"header_title": "Our Place 🏠", "header_subtitle": f"You, {partner}", "mode": "house"},
    }


def _step_chores(user):
    """Step 13: Delegates to existing chores flow."""
    # ponytail: return signal to web.py to use existing chore solver
    return {
        "messages": "__chores__",
        "ui_patch": {"header_title": "Our Place 🏠", "header_subtitle": f"You, {_partner_name(user)}", "mode": "house"},
    }


def reset(user=None):
    """Reset state for one user or all."""
    if user:
        _state.pop(user, None)
    else:
        _state.clear()
