"""Squad Up — Slack bot for multi-agent negotiation.

Slash command: /squad <feature> [args]
Features: class, study, plans, chores
Socket Mode — no public URL needed.

    SLACK_BOT_TOKEN=xoxb-... SLACK_APP_TOKEN=xapp-... python bot.py
"""

import os
import re
import logging

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

import agents
import blocks
import llm
import negotiator
import solvers
import asu_search
from privacy import ALLOWED

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("squad-up")

app = App(token=os.environ["SLACK_BOT_TOKEN"])

# Load student profiles on startup
agents.load_profiles()

# Map slack user IDs to student IDs (for demo: reverse lookup from profiles)
def _slack_to_student(slack_user_id):
    """Find student ID by Slack user ID. Fallback: first profile for demo."""
    for sid, p in agents.get_profiles().items():
        if p.get("slack_id") == slack_user_id:
            return sid
    # Demo fallback: cycle through students
    return None


def _all_participants_in_channel():
    """For demo: return all student IDs."""
    return agents.all_student_ids()


# ---------------------------------------------------------------------------
# /squad command
# ---------------------------------------------------------------------------

@app.command("/squad")
def handle_squad(ack, command, say, client):
    ack()
    text = (command.get("text") or "").strip()
    channel = command["channel_id"]
    user_id = command["user_id"]

    parts = text.split(None, 1)
    feature = parts[0].lower() if parts else ""
    args = parts[1] if len(parts) > 1 else ""

    if feature not in ("class", "study", "plans", "chores"):
        client.chat_postEphemeral(
            channel=channel, user=user_id,
            text="Usage: `/squad <class|study|plans|chores> [args]`\n"
                 "Examples:\n"
                 "  `/squad class CSE310` — coordinate class sections\n"
                 "  `/squad study CSE310` — find study time\n"
                 "  `/squad plans` — plan event attendance\n"
                 "  `/squad chores` — split household chores",
        )
        return

    # Privacy consent ephemeral
    allowed = ALLOWED[feature]
    all_fields = {"id", "name", "campus", "courses", "schedule", "available_slots",
                  "interested", "has_conflict", "chore_preferences",
                  "personality", "private_notes", "interests"}
    hidden = all_fields - allowed

    client.chat_postEphemeral(
        channel=channel, user=user_id,
        blocks=blocks.privacy_consent(feature, allowed, hidden),
        text=f"Squad Up — {feature}: review what gets shared",
    )

    # Store pending command context (keyed by user for simplicity)
    # ponytail: module-level dict, good enough for demo
    _pending_commands[user_id] = {
        "feature": feature,
        "args": args,
        "channel": channel,
    }


_pending_commands = {}


# ---------------------------------------------------------------------------
# Consent buttons
# ---------------------------------------------------------------------------

@app.action("consent_start")
def handle_consent_start(ack, body, client, say):
    ack()
    user_id = body["user"]["id"]
    pending = _pending_commands.pop(user_id, None)
    if not pending:
        return

    feature = pending["feature"]
    args = pending["args"]
    channel = pending["channel"]

    # Delete ephemeral can't be done, but we proceed
    client.chat_postEphemeral(
        channel=channel, user=user_id,
        text=f"Starting {feature} negotiation...",
    )

    # Run the feature
    if feature == "class":
        _run_class(channel, args, client, say)
    elif feature == "study":
        _run_study(channel, args, client, say)
    elif feature == "plans":
        _run_plans(channel, client, say)
    elif feature == "chores":
        _run_chores(channel, client, say)


@app.action("consent_cancel")
def handle_consent_cancel(ack, body, client):
    ack()
    user_id = body["user"]["id"]
    _pending_commands.pop(user_id, None)
    client.chat_postEphemeral(
        channel=body["channel"]["id"], user=user_id,
        text="Cancelled.",
    )


# ---------------------------------------------------------------------------
# Feature runners
# ---------------------------------------------------------------------------

def _run_class(channel, args, client, say):
    """Run class section coordination."""
    # Parse course from args: "CSE310" or "CSE 310"
    match = re.match(r"([A-Za-z]+)\s*(\d+)", args)
    if not match:
        say(channel=channel, text="Usage: `/squad class CSE310`")
        return

    subject, number = match.group(1).upper(), match.group(2)
    participants = solvers.students_in_course(subject, number)

    if len(participants) < 2:
        say(channel=channel, text=f"Need at least 2 students in {subject} {number}. Found: {len(participants)}")
        return

    # Fetch sections from ASU
    try:
        term = asu_search.get_current_term()
        result = asu_search.search_classes(term, subject=subject, catalog_number=number, open_only=True)
        sections = result.get("classes", [])
    except Exception as e:
        logger.warning(f"ASU API error: {e}. Using mock sections.")
        sections = [{"section": "1001", "days": "MW", "time": "9:00-10:15",
                      "seats_open": 50, "location": "TEMPE", "course": f"{subject} {number}"}]

    proposal = solvers.solve_class(subject, number, sections, participants)
    _post_proposal(channel, "class", participants, proposal, client, say,
                   solver_fn=solvers.solve_class,
                   solver_args={"subject": subject, "number": number,
                                "sections": sections, "participants": participants})


def _run_study(channel, args, client, say):
    """Run study group scheduling."""
    match = re.match(r"([A-Za-z]+)\s*(\d+)", args)
    if not match:
        say(channel=channel, text="Usage: `/squad study CSE310`")
        return

    subject, number = match.group(1).upper(), match.group(2)
    course_key = f"{subject}{number}"
    participants = solvers.students_in_course(subject, number)

    if len(participants) < 2:
        say(channel=channel, text=f"Need at least 2 students in {course_key}. Found: {len(participants)}")
        return

    proposal = solvers.solve_study(course_key, participants)
    _post_proposal(channel, "study", participants, proposal, client, say,
                   solver_fn=solvers.solve_study,
                   solver_args={"course_key": course_key, "participants": participants})


def _run_plans(channel, client, say):
    """Run event squad planning."""
    participants = _all_participants_in_channel()

    try:
        result = asu_search.search_events(limit=3)
        events = result.get("events", [])
    except Exception as e:
        logger.warning(f"ASU events API error: {e}. Using mock event.")
        events = [{"title": "Fall Career Fair", "date": "Nov 1",
                    "time": "10am-3pm", "location": "Tempe campus"}]

    if not events:
        say(channel=channel, text="No upcoming events found.")
        return

    event = events[0]
    proposal = solvers.solve_plans(event, participants)
    _post_proposal(channel, "plans", participants, proposal, client, say,
                   solver_fn=solvers.solve_plans,
                   solver_args={"event": event, "participants": participants})


def _run_chores(channel, client, say):
    """Run chore split."""
    participants = _all_participants_in_channel()
    proposal = solvers.solve_chores(participants)
    _post_proposal(channel, "chores", participants, proposal, client, say,
                   solver_fn=solvers.solve_chores,
                   solver_args={"participants": participants})


def _post_proposal(channel, feature, participants, proposal, client, say,
                   solver_fn, solver_args):
    """Generate agent messages, create negotiation, post to channel."""
    # Generate agent messages via LLM
    agent_msgs = {}
    for sid in participants:
        try:
            profile = agents.get_profile(sid)
            context = f"Comment on this {feature} proposal: {proposal}"
            agent_msgs[sid] = llm.agent_speak(profile, feature, context)
        except Exception as e:
            logger.warning(f"LLM error for {sid}: {e}")
            agent_msgs[sid] = f"{agents.get_profile(sid)['name']} is reviewing the proposal."

    # Format proposal text
    proposal_text = _format_proposal(feature, proposal)

    # Create negotiation
    neg = negotiator.create(feature, channel, participants, proposal,
                            solver_fn, solver_args)

    # Post to channel
    say(
        channel=channel,
        blocks=blocks.proposal_message(
            feature, 1, agent_msgs, proposal_text, participants, neg["id"]
        ),
        text=f"{feature.title()} proposal — Round 1",
    )


def _format_proposal(feature, proposal):
    """Format proposal dict into readable text."""
    if feature == "class":
        sec = proposal.get("proposal", {})
        if isinstance(sec, dict):
            return (f"Section {sec.get('section', '?')} — {sec.get('days', '')} "
                    f"{sec.get('time', '')} ({proposal.get('attendance', '')} can attend)")
        return str(proposal.get("reason", "No sections available"))

    elif feature == "study":
        slot = proposal.get("proposal", "?")
        loc = proposal.get("location", "")
        att = proposal.get("attendance", "")
        return f"{slot} at {loc} ({att} can attend)"

    elif feature == "plans":
        event = proposal.get("event", {})
        n = len(proposal.get("who_can_go", []))
        total = len(proposal.get("who_can_go", [])) + len(proposal.get("who_has_conflict", []))
        return f"{event.get('title', '?')} — {event.get('date', '')} ({n}/{total} available)"

    elif feature == "chores":
        lines = []
        for chore, sid in proposal.get("assignments", {}).items():
            name = agents.get_profile(sid)["name"] if sid else "unassigned"
            lines.append(f"{chore}: {name}")
        return "\n".join(lines) if lines else "No chores to assign"

    return str(proposal)


# ---------------------------------------------------------------------------
# Vote handlers (approve/veto)
# ---------------------------------------------------------------------------

@app.action(re.compile(r"approve_neg_\w+"))
def handle_approve(ack, body, client, say):
    ack()
    action = body["actions"][0]
    neg_id = action["action_id"].replace("approve_", "")
    student_id = action["value"]
    channel = body["channel"]["id"]

    neg = negotiator.approve(neg_id, student_id)
    if not neg:
        return

    name = agents.get_profile(student_id)["name"]

    if neg["status"] == "signed":
        proposal = negotiator.current_proposal(neg_id)
        try:
            summary = llm.outcome_message(neg["feature"], proposal, "signed")
        except Exception:
            summary = _format_proposal(neg["feature"], proposal)

        say(channel=channel, blocks=blocks.outcome_signed(neg["feature"], summary),
            text="Agreement signed!")
    else:
        say(channel=channel, text=f":white_check_mark: {name}'s agent approved.")


@app.action(re.compile(r"veto_neg_\w+"))
def handle_veto(ack, body, client, say):
    ack()
    action = body["actions"][0]
    neg_id = action["action_id"].replace("veto_", "")
    student_id = action["value"]
    channel = body["channel"]["id"]
    user_id = body["user"]["id"]

    # Store veto context for DM flow
    _pending_vetoes[user_id] = {"neg_id": neg_id, "student_id": student_id, "channel": channel}

    # DM the user asking for private reason
    try:
        dm = client.conversations_open(users=[user_id])
        dm_channel = dm["channel"]["id"]
        client.chat_postMessage(
            channel=dm_channel,
            blocks=blocks.veto_dm(),
            text="Why did you veto? (This stays private)",
        )
    except Exception as e:
        logger.warning(f"Could not DM {user_id}: {e}")
        # Fallback: veto with default reason
        _process_veto(neg_id, student_id, "", channel, say)


_pending_vetoes = {}


@app.action("veto_reason_submit")
def handle_veto_reason(ack, body, client, say):
    ack()
    user_id = body["user"]["id"]
    pending = _pending_vetoes.pop(user_id, None)
    if not pending:
        return

    # Extract reason from input
    state = body.get("state", {}).get("values", {})
    reason = ""
    for block_vals in state.values():
        for input_val in block_vals.values():
            reason = input_val.get("value", "")

    _process_veto(pending["neg_id"], pending["student_id"], reason,
                  pending["channel"], say)


def _process_veto(neg_id, student_id, private_reason, channel, say):
    """Process veto: get safe message, re-propose, post to channel."""
    # Generate safe public message
    try:
        public_reason = llm.safe_veto_message(private_reason) if private_reason else "Not available at that time"
    except Exception:
        public_reason = "Not available at that time"

    neg = negotiator.veto(neg_id, student_id, private_reason, public_reason)
    if not neg:
        return

    name = agents.get_profile(student_id)["name"]

    if neg["status"] == "failed":
        try:
            summary = llm.outcome_message(neg["feature"], negotiator.current_proposal(neg_id), "failed")
        except Exception:
            summary = "Could not reach agreement after 3 rounds."
        say(channel=channel, blocks=blocks.outcome_failed(neg["feature"], summary),
            text="Negotiation failed")
        return

    # New round — post updated proposal
    proposal = negotiator.current_proposal(neg_id)
    round_num = negotiator.current_round_num(neg_id)

    agent_msgs = {}
    for sid in neg["participants"]:
        try:
            profile = agents.get_profile(sid)
            context = f"Round {round_num}: The proposal changed after {name} vetoed. New proposal: {proposal}"
            agent_msgs[sid] = llm.agent_speak(profile, neg["feature"], context)
        except Exception:
            agent_msgs[sid] = f"{agents.get_profile(sid)['name']} is reviewing."

    proposal_text = _format_proposal(neg["feature"], proposal)

    say(
        channel=channel,
        blocks=blocks.proposal_message(
            neg["feature"], round_num, agent_msgs, proposal_text,
            neg["participants"], neg["id"]
        ),
        text=f"{neg['feature'].title()} — Round {round_num} (after {name}'s veto: {public_reason})",
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    logger.info("Squad Up bot starting (Socket Mode)...")
    handler.start()
