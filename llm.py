"""Claude API wrapper for agent reasoning and negotiation messages."""

import os

from dotenv import load_dotenv
load_dotenv()

MODEL = "claude-haiku-5-5"
MAX_TOKENS = 300

from anthropic import Anthropic
client = Anthropic()  # fails loudly if ANTHROPIC_API_KEY missing


def _extract_text(resp):
    """Pull text from response, skipping thinking blocks."""
    parts = []
    for block in resp.content:
        if getattr(block, "type", None) == "text" and block.text.strip():
            parts.append(block.text.strip())
    return " ".join(parts)


_CHAT_SYSTEM = (
    "You are RoomieAgent, a chill AI assistant for ASU students sharing a place. "
    "Keep replies casual, concise (2-4 sentences), ASU-flavored. "
    "You can help with: splitting chores, finding study groups, picking class sections, and making plans. "
    "If someone seems unsure what to do, suggest a feature: \"wanna split chores?\", \"study CSE310?\", etc. "
    "One emoji max per message."
)


def chat(user_id, history):
    """Free-form conversation. history = list of {role, content}."""
    msgs = history if history else [{"role": "user", "content": "Say hi to the group."}]
    resp = client.messages.create(
        model=MODEL, max_tokens=MAX_TOKENS,
        system=_CHAT_SYSTEM,
        messages=msgs,
    )
    return _extract_text(resp) or "Hey! I'm RoomieAgent — I can help split chores, find study groups, and more."


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


def agent_speak(profile, feature, context):
    """Have an agent generate a natural message about their stance."""
    allowed = FEATURE_ALLOWED.get(feature, set())
    system = _system_prompt(profile, feature, allowed)
    resp = client.messages.create(
        model=MODEL, max_tokens=MAX_TOKENS, system=system,
        messages=[{"role": "user", "content": context}],
    )
    return _extract_text(resp) or "Sounds good to me!"


def negotiation_message(feature, proposal, participants_info):
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


def roommate_message(context):
    """LLM-generated message for roommate matching events."""
    resp = client.messages.create(
        model=MODEL, max_tokens=MAX_TOKENS,
        system=(
            "You are RoomieAgent, a friendly roommate matching bot for ASU students. "
            "Write a short, encouraging message (1-2 sentences). Be casual, ASU-flavored. One emoji max."
        ),
        messages=[{"role": "user", "content": context}],
    )
    return _extract_text(resp) or "You two are going to have a great semester!"


if __name__ == "__main__":
    from agents import load_profiles, get_profile
    load_profiles()
    profile = get_profile("shreeya")
    msg = agent_speak(profile, "study", "Share your availability for a CSE310 study session this week.")
    print(f"Shreeya's agent: {msg}")
    print("Mode: LIVE")
