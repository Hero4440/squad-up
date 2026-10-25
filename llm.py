"""Claude API wrapper for agent reasoning and negotiation messages.

Set MOCK_LLM=1 to skip API calls and use canned responses (free, instant).
"""

import os
import random

from dotenv import load_dotenv
load_dotenv()

MOCK = os.environ.get("MOCK_LLM", "0") == "1"
MODEL = "claude-haiku-5-5"
MAX_TOKENS = 300

def _extract_text(resp):
    """Pull text from response, skipping thinking blocks."""
    parts = []
    for block in resp.content:
        if getattr(block, "type", None) == "text" and block.text.strip():
            parts.append(block.text.strip())
    return " ".join(parts)

client = None
if not MOCK:
    try:
        from anthropic import Anthropic
        client = Anthropic()
        # Quick connectivity check
        client.messages.create(
            model=MODEL, max_tokens=5,
            messages=[{"role": "user", "content": "hi"}],
        )
    except Exception as e:
        import logging
        logging.getLogger("squad-up").warning(f"LLM unavailable ({e}), falling back to mock mode.")
        MOCK = True
        client = None


def _system_prompt(profile, feature, allowed_fields):
    private = set(profile.keys()) - allowed_fields - {"id"}
    return (
        f"You are {profile['name']}'s personal AI agent in a Slack group chat. "
        f"You know their full profile but ONLY share what's in these fields: {', '.join(sorted(allowed_fields))}. "
        f"NEVER reveal: {', '.join(sorted(private))}. "
        f"Speak naturally in 1-2 sentences. Be specific to ASU campus life. "
        f"Current feature: {feature}."
    )


FEATURE_ALLOWED = {
    "class":  {"id", "name", "campus", "courses"},
    "study":  {"id", "name", "campus", "available_slots"},
    "plans":  {"id", "name", "campus", "interested", "has_conflict"},
    "chores": {"id", "name", "chore_preferences"},
}

# --- Mock responses keyed by (feature, personality hint) ---

_MOCK_STUDY = {
    "shreeya": [
        "I'm free Friday mornings on Tempe campus — library works for me!",
        "Friday 10am is perfect, I'll grab a study room at Hayden.",
    ],
    "rishi": [
        "Friday works for me! I can take the light rail from Downtown.",
        "I'm down for Hayden Library, I just need to bus over from Downtown.",
    ],
    "tejas": [
        "Fridays are chill for me, Tempe campus — let's do it.",
        "I'm free Friday morning, Hayden sounds good.",
    ],
}

_MOCK_CHORES = {
    "shreeya": [
        "I'd rather vacuum than touch the bathroom, honestly.",
        "Vacuum and trash are fine with me!",
    ],
    "rishi": [
        "I'll take out the trash, just don't put me on kitchen duty.",
        "Trash is easy, I'm good with that.",
    ],
    "tejas": [
        "Bathroom doesn't bother me. Kitchen and dishes are fine too.",
        "I can handle the bathroom, no problem.",
    ],
}

_MOCK_CLASS = {
    "shreeya": [
        "The MW morning section works with my schedule on Tempe campus.",
        "I'm already in section 1001, mornings work great for me.",
    ],
    "rishi": [
        "I need an afternoon section since I have morning classes Downtown.",
        "Afternoon sections are better — I commute from Downtown.",
    ],
    "tejas": [
        "I'm flexible, morning or afternoon works for me on Tempe.",
        "Either section is fine, I'm on Tempe campus.",
    ],
}

_MOCK_PLANS = {
    "shreeya": [
        "I'd love to go! Tempe campus is easy for me.",
        "Count me in, I've been wanting to check this out.",
    ],
    "rishi": [
        "I'm in! Can we carpool from Downtown?",
        "Sounds fun, I'll find a ride from Downtown.",
    ],
    "tejas": [
        "I'm down, Tempe campus is right here for me.",
        "Yeah let's go, I can walk from my dorm.",
    ],
}

_MOCK_STUDY["arjun"] = [
    "Morning sessions on Tempe campus work for me — library or union.",
    "I'm free most mornings, Tempe is convenient.",
]
_MOCK_CHORES["arjun"] = [
    "I'll handle kitchen duty, I like keeping it clean anyway.",
    "Kitchen's my thing. Dishes are fine too.",
]
_MOCK_CLASS["arjun"] = [
    "Morning section works great for me, I'm on Tempe campus.",
    "Early morning sections fit my schedule on Tempe.",
]
_MOCK_PLANS["arjun"] = [
    "I'm in! Tempe campus is easy for me.",
    "Sounds good, I can walk from my place.",
]

_MOCK_FEATURES = {
    "study": _MOCK_STUDY,
    "chores": _MOCK_CHORES,
    "class": _MOCK_CLASS,
    "plans": _MOCK_PLANS,
}


def agent_speak(profile, feature, context):
    """Have an agent generate a natural message about their stance."""
    if MOCK:
        sid = profile.get("id", "shreeya")
        pool = _MOCK_FEATURES.get(feature, _MOCK_STUDY).get(sid, ["Looks good to me."])
        return random.choice(pool)

    allowed = FEATURE_ALLOWED.get(feature, set())
    system = _system_prompt(profile, feature, allowed)
    resp = client.messages.create(
        model=MODEL, max_tokens=MAX_TOKENS, system=system,
        messages=[{"role": "user", "content": context}],
    )
    return _extract_text(resp) or "Sounds good to me!"


def negotiation_message(feature, proposal, participants_info):
    if MOCK:
        return f"Here's what I came up with for {feature}!"

    resp = client.messages.create(
        model=MODEL, max_tokens=MAX_TOKENS,
        system=(
            "You format negotiation proposals for a Slack group chat of ASU students. "
            "Be concise, friendly, use emoji sparingly. Include key details. "
            "Never reveal private reasons for conflicts — just say they have a conflict."
        ),
        messages=[{"role": "user", "content": (
            f"Feature: {feature}\nProposal: {proposal}\n"
            f"Participants: {participants_info}\n\nWrite a brief Slack message announcing this proposal."
        )}],
    )
    return _extract_text(resp) or f"Here's what I came up with for {feature}!"


def safe_veto_message(private_reason):
    if MOCK:
        return "That time doesn't work for me."

    resp = client.messages.create(
        model=MODEL, max_tokens=100,
        system=(
            "Convert a private reason into a safe, vague public message. "
            "Never reveal specifics about work, health, personal life. "
            "Just say something like 'That time doesn't work for me' or "
            "'I have a scheduling conflict then'. One sentence max."
        ),
        messages=[{"role": "user", "content": f"Private reason: {private_reason}"}],
    )
    return _extract_text(resp) or "That time doesn't work for me."


def outcome_message(feature, result, status):
    if MOCK:
        if status == "signed":
            return "Everyone's on board — locked in!"
        return "Couldn't find something that works for everyone. Maybe hash it out in person?"

    system = (
        "Write a brief celebratory Slack message confirming the agreement. One emoji max."
        if status == "signed" else
        "Write a brief Slack message saying the group couldn't agree. Suggest meeting in person. Friendly tone."
    )
    resp = client.messages.create(
        model=MODEL, max_tokens=200, system=system,
        messages=[{"role": "user", "content": f"Feature: {feature}\nResult: {result}"}],
    )
    fallback = "Everyone's on board — locked in!" if status == "signed" else "Couldn't find something that works for everyone."
    return _extract_text(resp) or fallback


_MOCK_ROOMMATE = [
    "You two are going to have a great semester!",
    "This match looks solid — compatible on the things that matter most!",
    "Great news: you're a strong match!",
]


def roommate_message(context):
    """LLM-generated message for roommate matching events."""
    if MOCK:
        return random.choice(_MOCK_ROOMMATE)

    resp = client.messages.create(
        model=MODEL, max_tokens=MAX_TOKENS,
        system=(
            "You are RoomieAgent, a friendly roommate matching bot for ASU students. "
            "Write a short, encouraging message (1-2 sentences). Be casual, ASU-flavored. One emoji max."
        ),
        messages=[{"role": "user", "content": context}],
    )
    return _extract_text(resp) or random.choice(_MOCK_ROOMMATE)


if __name__ == "__main__":
    from agents import load_profiles, get_profile
    load_profiles()
    profile = get_profile("shreeya")
    msg = agent_speak(profile, "study", "Share your availability for a CSE310 study session this week.")
    print(f"Shreeya's agent: {msg}")
    print(f"Mode: {'MOCK' if MOCK else 'LIVE'}")
