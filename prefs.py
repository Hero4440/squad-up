"""Agent settings for whoever is using the web UI — per-user.

Answers are saved to profiles/you_prefs_{user}.json and layered over that person's
entry in students.json, so the solvers keep reading the same fields
(chore_preferences, campus) they always did. Hard "can't do" answers go into
chore_blocked, which web.py hands to the chore solver as constraints.
"""

import json
import os
import re

import agents

BASE = os.path.dirname(os.path.abspath(__file__))

CHORES = ["cleaning", "dishes", "dusting", "cooking"]
LEVELS = {"cant": None, "hate": 1, "fine": 3, "happy": 5}
VIBES = ["chill", "hype", "formal"]
CAMPUSES = ["TEMPE", "DOWNTOWN", "POLY", "WEST"]
ACCESSORIES = ["none", "beret", "beanie", "sunglasses", "glasses", "headphones", "frog"]
COLORS = ["#f08a24", "#3b5bdb", "#8ccf2f", "#e5443f", "#8a55d6", "#f5c32c", "#e83e9c", "#f4f1ea"]

# ponytail: per-user state dict
_states = {}


def _path_for(user_id):
    return os.path.join(BASE, "profiles", f"you_prefs_{user_id}.json")


def you_id(user_id=None):
    if user_id:
        return user_id
    return os.environ.get("SQUAD_YOU") or agents.all_student_ids()[0]


def _level_for(score):
    if score <= 2:
        return "hate"
    if score >= 4:
        return "happy"
    return "fine"


def _load(user_id):
    profile = agents.get_profile(user_id)
    scores = profile.get("chore_preferences", {})
    st = {
        "agent_name": "",
        "vibe": "chill",
        "campus": profile.get("campus", "TEMPE"),
        "accessory": "",
        "color": "",
        "chores": {c: _level_for(scores.get(c, 3)) for c in CHORES},
        "chores_set": False,
    }
    path = _path_for(user_id)
    try:
        with open(path) as f:
            saved = json.load(f)
    except (OSError, ValueError):
        return st
    chores = saved.pop("chores", {})
    st.update({k: v for k, v in saved.items() if k in st})
    st["chores"].update({c: l for c, l in chores.items() if c in CHORES and l in LEVELS})
    return st


def get(user_id=None):
    uid = you_id(user_id)
    if uid not in _states:
        _states[uid] = _load(uid)
    return _states[uid]


def apply(user_id=None):
    """Push the saved answers onto the live profile."""
    uid = you_id(user_id)
    st = get(uid)
    profile = agents.get_profile(uid)
    profile["campus"] = st["campus"]
    profile["chore_preferences"] = {c: (LEVELS[l] or 1) for c, l in st["chores"].items()}
    profile["chore_blocked"] = [c for c, l in st["chores"].items() if l == "cant"]


def save(update, user_id=None):
    uid = you_id(user_id)
    st = dict(get(uid))
    st["chores"] = dict(st["chores"])

    if "agent_name" in update:
        st["agent_name"] = str(update["agent_name"]).strip()[:24]
    if update.get("vibe") in VIBES:
        st["vibe"] = update["vibe"]
    if update.get("campus") in CAMPUSES:
        st["campus"] = update["campus"]
    if update.get("accessory") in ACCESSORIES:
        st["accessory"] = update["accessory"]
    if re.fullmatch(r"#[0-9a-fA-F]{6}", str(update.get("color", ""))):
        st["color"] = update["color"]
    answered = update.get("chores") or {}
    for chore, level in answered.items():
        if chore in CHORES and level in LEVELS:
            st["chores"][chore] = level
    if answered:
        st["chores_set"] = True

    _states[uid] = st
    path = _path_for(uid)
    with open(path, "w") as f:
        json.dump(st, f, indent=2)
    apply(uid)
    return st


def public(user_id=None):
    uid = you_id(user_id)
    me = agents.get_profile(uid)
    return {
        "you": {"id": uid, "name": me["name"]},
        **get(uid),
        "default_look": default_look(uid),
        "options": {"chores": CHORES, "vibes": VIBES, "campuses": CAMPUSES,
                    "accessories": ACCESSORIES, "colors": COLORS},
    }


def chores_set(user_id=None):
    return get(you_id(user_id))["chores_set"]


def reset_chores(user_id=None):
    """Reset chores_set flag so user gets asked again on fresh session."""
    uid = you_id(user_id)
    st = get(uid)
    st["chores_set"] = False
    _states[uid] = st
    path = _path_for(uid)
    with open(path, "w") as f:
        json.dump(st, f, indent=2)


def agent_label(sid):
    """Custom display name for the user's agent (None for everyone else)."""
    if sid in _states:
        return _states[sid].get("agent_name") or None
    return None


DEFAULT_LOOKS = {
    "shreeya": ("sunglasses", "#e07c5a"),
    "rishi": ("beret", "#5aa8e0"),
    "tejas": ("frog", "#7bc47f"),
    "arjun": ("glasses", "#8a55d6"),
    "you": ("none", "#06cf9c"),
}


def default_look(user_id=None):
    uid = you_id(user_id)
    acc, color = DEFAULT_LOOKS.get(uid, ("none", "#8a55d6"))
    return {"accessory": acc, "color": color}


def look(sid):
    """Custom avatar choices for the user's agent ({} for everyone else / unset)."""
    if sid not in _states:
        return {}
    st = _states[sid]
    return {k: st[k] for k in ("accessory", "color") if st[k]}


def tone_hint(sid):
    if sid in _states and _states[sid].get("vibe", "chill") != "chill":
        return f" Speak in a {_states[sid]['vibe']} tone."
    return ""


def blocked_constraints(participants):
    """(student_id, chore) pairs the chore solver must never assign."""
    out = []
    for sid in participants:
        for chore in agents.get_profile(sid).get("chore_blocked", []):
            out.append((sid, chore))
    return out
