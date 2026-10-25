"""RoomieAgent — localhost web UI (stdlib HTTP server).

Serves chat UI + JSON API.
Wires to existing solvers, negotiator, llm, agents, privacy.
Adds scenario engine for roommate matching demo.

    python3 web.py
    open http://localhost:8888?user=shreeya
"""

import json
import os
import re
import logging
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import agents
import llm
import negotiator
import solvers
import asu_search
import prefs
import scenarios
from privacy import ALLOWED

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("roomie-web")

PORT = int(os.environ.get("PORT", 8888))

agents.load_profiles()

# Per-user state for chores negotiation
_user_state = {}  # user -> {neg_id, awaiting_veto_reason}

# Per-user conversation history for free-form chat
_chat_history = {}  # user -> list of {role, content}
_MAX_HISTORY = 20

# Student metadata for frontend
STUDENT_META = {
    "shreeya": {"name": "Shreeya", "initial": "S", "color": "#e07c5a", "accessory": "sunglasses"},
    "rishi":   {"name": "Rishi",   "initial": "R", "color": "#5aa8e0", "accessory": "beret"},
    "tejas":   {"name": "Tejas",   "initial": "T", "color": "#7bc47f", "accessory": "frog"},
    "arjun":   {"name": "Arjun",   "initial": "A", "color": "#8a55d6", "accessory": "glasses"},
}


def _ustate(user):
    if user not in _user_state:
        _user_state[user] = {"neg_id": None, "awaiting_veto_reason": False}
    return _user_state[user]


def _participant_info(sid):
    meta = STUDENT_META.get(sid)
    if meta:
        return meta
    p = agents.get_profile(sid)
    return {"name": p["name"], "initial": p["name"][0], "color": "#999"}


def _look(sid):
    """Avatar for an agent: its built-in blob unless the user restyled theirs."""
    meta = STUDENT_META.get(sid, {})
    mine = prefs.look(sid)
    return {
        "accessory": mine.get("accessory") or meta.get("accessory", "none"),
        "color": mine.get("color") or meta.get("color", "#999"),
    }


_CLASSIC_IDS = ["shreeya", "rishi", "tejas"]

def _all_participants(flow=None):
    if flow == "classic":
        return _CLASSIC_IDS
    return agents.all_student_ids()


def _format_proposal_title(feature, proposal):
    """Short title for proposal card header."""
    if feature == "class":
        sec = proposal.get("proposal", {})
        if isinstance(sec, dict):
            return f"{sec.get('course', '')} Section {sec.get('section', '?')}"
        return "Class Section"
    elif feature == "study":
        return f"Study Group — {proposal.get('course', '')}"
    elif feature == "plans":
        return proposal.get("event", {}).get("title", "Event Plan")
    elif feature == "chores":
        return "Weekly Chore Split"
    return feature.title()


def _format_proposal_body(feature, proposal, user_id=None):
    """Detailed body for proposal card."""
    if feature == "class":
        sec = proposal.get("proposal", {})
        if isinstance(sec, dict):
            lines = [
                f"{sec.get('days', '')} {sec.get('time', '')}",
                f"Location: {sec.get('location', 'TBD')}",
                f"Seats open: {sec.get('seats_open', '?')}",
                f"Attendance: {proposal.get('attendance', '')}",
            ]
            return "\n".join(lines)
        return proposal.get("reason", "No sections available")
    elif feature == "study":
        return "\n".join([
            f"Time: {proposal.get('proposal', '?')}",
            f"Location: {proposal.get('location', '')}",
            f"Attendance: {proposal.get('attendance', '')}",
        ])
    elif feature == "plans":
        event = proposal.get("event", {})
        lines = [
            f"Date: {event.get('date', '')} {event.get('time', '')}",
            f"Location: {event.get('location', '')}",
            f"Attendance: {proposal.get('attendance', '')}",
        ]
        if proposal.get("carpool_groups"):
            for campus, sids in proposal["carpool_groups"].items():
                names = ["You" if s == user_id else agents.get_profile(s)["name"].split()[0] for s in sids]
                lines.append(f"Carpool ({campus}): {', '.join(names)}")
        return "\n".join(lines)
    elif feature == "chores":
        lines = []
        for chore, sid in proposal.get("assignments", {}).items():
            name = "You" if sid == user_id else (agents.get_profile(sid)["name"].split()[0] if sid else "unassigned")
            pref = proposal.get("explanation", {}).get(chore, {}).get("their_preference", "?")
            lines.append(f"{name}: {chore} (preference: {pref}/5)")
        return "\n".join(lines)
    return str(proposal)


def _format_proposal_explanation(feature, proposal):
    """Why this plan — short explanation."""
    if feature == "class":
        return f"Best section by attendance: {proposal.get('attendance', '')} can attend with no schedule conflicts."
    elif feature == "study":
        att = proposal.get("attendance", "")
        loc = proposal.get("location", "")
        return f"Slot with highest attendance ({att}). Location by campus majority → {loc}."
    elif feature == "plans":
        return f"Checked schedules: {proposal.get('attendance', '')} available. Grouped by campus for carpool."
    elif feature == "chores":
        mh = proposal.get("min_happiness", "?")
        return f"Maximin fairness — each chore goes to who minds it least. Lowest happiness: {mh}/5."
    return ""


def _build_proposal_card(feature, proposal, participants, neg_id, round_num=1, user_id=None):
    """Build rich proposal card message."""
    participant_status = []
    for sid in participants:
        info = _participant_info(sid)
        participant_status.append({
            "id": sid,
            "name": "You" if sid == user_id else info["name"].split()[0],
            "initial": info["initial"],
            "color": info["color"],
            "status": "pending",
        })

    return {
        "type": "proposal_card",
        "label": feature.upper(),
        "title": _format_proposal_title(feature, proposal),
        "body": _format_proposal_body(feature, proposal, user_id),
        "explanation": _format_proposal_explanation(feature, proposal),
        "participants": participant_status,
        "neg_id": neg_id,
        "round": round_num,
    }


def _build_votes(participants, agent_msgs):
    """Build agent vote chips."""
    votes = []
    for sid in participants:
        info = _participant_info(sid)
        msg = agent_msgs.get(sid, "reviewing...")
        short = msg if len(msg) <= 60 else msg[:57] + "..."
        votes.append({
            "id": sid,
            "initial": info["initial"],
            "color": info["color"],
            "name": info["name"].split()[0],
            "agent_label": prefs.agent_label(sid),
            "look": _look(sid),
            "text": short,
            "approved": True,
        })
    return {"type": "votes", "votes": votes}


def _chore_check_card(user_id):
    st = prefs.get(user_id)
    return {
        "type": "pref_card",
        "topic": "chores",
        "title": "Chores: where do you stand?",
        "subtitle": "Pre-filled from your profile. Only change what's off. Nobody else sees your picks.",
        "items": [{"key": c, "label": c.title(), "level": st["chores"][c]} for c in prefs.CHORES],
    }


def _run_feature(feature, args, user_id, flow=None):
    """Run a feature solver, return list of message dicts for the UI."""
    us = _ustate(user_id)
    messages = []

    if feature == "chores" and not prefs.chores_set(user_id):
        return [
            {"type": "bot", "text": "Quick — how do you feel about each chore? Tap one per row."},
            _chore_check_card(user_id),
        ]

    allowed = ALLOWED[feature]
    hidden = ["full schedule", "private notes", "personality"]
    messages.append({
        "type": "system",
        "text": f"Privacy: sharing {', '.join(sorted(allowed))}. NOT sharing: {', '.join(hidden)}.",
    })

    if feature == "class":
        match = re.match(r"([A-Za-z]+)\s*(\d+)", args)
        if not match:
            return [{"type": "system", "text": "Usage: class CSE310"}]
        subject, number = match.group(1).upper(), match.group(2)
        participants = solvers.students_in_course(subject, number)
        if len(participants) < 2:
            return [{"type": "system", "text": f"Need 2+ students in {subject} {number}. Found: {len(participants)}"}]
        try:
            term = asu_search.get_current_term()
            result = asu_search.search_classes(term, subject=subject, catalog_number=number, open_only=True)
            sections = result.get("classes", [])
        except Exception as e:
            logger.warning(f"ASU API error: {e}. Using mock sections.")
            sections = [{"section": "1001", "days": "MW", "time": "9:00-10:15",
                         "seats_open": 50, "location": "TEMPE", "course": f"{subject} {number}"}]
        proposal = solvers.solve_class(subject, number, sections, participants)
        solver_fn, solver_args = solvers.solve_class, {
            "subject": subject, "number": number, "sections": sections, "participants": participants}

    elif feature == "study":
        match = re.match(r"([A-Za-z]+)\s*(\d+)", args)
        if not match:
            return [{"type": "system", "text": "Usage: study CSE310"}]
        subject, number = match.group(1).upper(), match.group(2)
        course_key = f"{subject}{number}"
        participants = solvers.students_in_course(subject, number)
        if len(participants) < 2:
            return [{"type": "system", "text": f"Need 2+ students in {course_key}. Found: {len(participants)}"}]
        proposal = solvers.solve_study(course_key, participants)
        solver_fn, solver_args = solvers.solve_study, {"course_key": course_key, "participants": participants}

    elif feature == "plans":
        participants = _all_participants(flow)
        try:
            result = asu_search.search_events(limit=3)
            events = result.get("events", [])
        except Exception as e:
            logger.warning(f"ASU events error: {e}. Using mock.")
            events = [{"title": "Fall Career Fair", "date": "Nov 1",
                       "time": "10am-3pm", "location": "Tempe campus"}]
        if not events:
            return [{"type": "system", "text": "No upcoming events found."}]
        event = events[0]
        proposal = solvers.solve_plans(event, participants)
        solver_fn, solver_args = solvers.solve_plans, {"event": event, "participants": participants}

    elif feature == "chores":
        participants = _all_participants(flow)
        hard_nos = prefs.blocked_constraints(participants)
        proposal = solvers.solve_chores(participants, hard_nos)
        solver_fn, solver_args = solvers.solve_chores, {"participants": participants}

    else:
        return [{"type": "system", "text": f"Unknown feature: {feature}"}]

    if proposal.get("proposal") is None and feature != "chores":
        messages.append({"type": "system", "text": proposal.get("reason", "No solution found.")})
        return messages

    messages.append({
        "type": "bot",
        "text": f"Checking schedules and preferences for {feature}...",
    })

    agent_msgs = {}
    other_participants = [sid for sid in participants if sid != user_id]
    for sid in other_participants:
        try:
            profile = agents.get_profile(sid)
            context = f"Comment on this {feature} proposal: {proposal}" + prefs.tone_hint(sid)
            agent_msgs[sid] = llm.agent_speak(profile, feature, context)
        except Exception as e:
            logger.warning(f"LLM error for {sid}: {e}")
            agent_msgs[sid] = f"{agents.get_profile(sid)['name']} is reviewing the proposal."

    messages.append(_build_votes(other_participants, agent_msgs))

    neg = negotiator.create(feature, "web", participants, proposal, solver_fn, solver_args)
    us["neg_id"] = neg["id"]
    if feature == "chores":
        neg["constraints"].extend(hard_nos)

    messages.append(_build_proposal_card(feature, proposal, participants, neg["id"], user_id=user_id))

    return messages


def _handle_approve(user_id):
    us = _ustate(user_id)
    neg = negotiator.get(us["neg_id"]) if us["neg_id"] else None
    if not neg or neg["status"] != "proposing":
        return [{"type": "system", "text": "Nothing to approve right now."}]

    messages = []
    for sid in neg["participants"]:
        negotiator.approve(us["neg_id"], sid)

    neg = negotiator.get(us["neg_id"])
    proposal = negotiator.current_proposal(us["neg_id"])

    try:
        summary = llm.outcome_message(neg["feature"], proposal, "signed")
    except Exception:
        summary = _format_proposal_title(neg["feature"], proposal) + " confirmed!"

    messages.append({"type": "signed", "text": summary})
    return messages


def _handle_veto(user_id):
    us = _ustate(user_id)
    neg = negotiator.get(us["neg_id"]) if us["neg_id"] else None
    if not neg or neg["status"] != "proposing":
        return [{"type": "system", "text": "Nothing to veto right now."}]
    return [{"type": "veto_prompt", "text": "Why do you want to veto? Your reason stays private."}]


def _handle_veto_reason(reason, user_id):
    us = _ustate(user_id)
    neg = negotiator.get(us["neg_id"]) if us["neg_id"] else None
    if not neg or neg["status"] != "proposing":
        return [{"type": "system", "text": "No active negotiation."}]

    student_id = neg["participants"][0]
    messages = []

    try:
        public_reason = llm.safe_veto_message(reason) if reason else "Not available at that time"
    except Exception:
        public_reason = "Not available at that time"

    neg = negotiator.veto(us["neg_id"], student_id, reason, public_reason)
    name = agents.get_profile(student_id)["name"]

    if neg["status"] == "failed":
        try:
            summary = llm.outcome_message(neg["feature"], negotiator.current_proposal(us["neg_id"]), "failed")
        except Exception:
            summary = "Could not reach agreement after 3 rounds."
        messages.append({"type": "failed", "text": summary})
        return messages

    proposal = negotiator.current_proposal(us["neg_id"])
    round_num = negotiator.current_round_num(us["neg_id"])

    messages.append({"type": "system", "text": f"Round {round_num} — {name} vetoed: \"{public_reason}\""})
    messages.append({"type": "bot", "text": "Re-negotiating with updated constraints..."})

    agent_msgs = {}
    others = [sid for sid in neg["participants"] if sid != user_id]
    for sid in others:
        try:
            profile = agents.get_profile(sid)
            context = f"Round {round_num}: proposal changed after veto. New proposal: {proposal}" + prefs.tone_hint(sid)
            agent_msgs[sid] = llm.agent_speak(profile, neg["feature"], context)
        except Exception:
            agent_msgs[sid] = f"{agents.get_profile(sid)['name']} is reviewing."

    messages.append(_build_votes(others, agent_msgs))
    messages.append(_build_proposal_card(
        neg["feature"], proposal, neg["participants"], us["neg_id"], round_num, user_id=user_id))

    return messages


def _handle_explain(user_id):
    us = _ustate(user_id)
    neg = negotiator.get(us["neg_id"]) if us["neg_id"] else None
    if not neg:
        return [{"type": "system", "text": "No active negotiation."}]
    proposal = negotiator.current_proposal(us["neg_id"])
    explanation = _format_proposal_explanation(neg["feature"], proposal)
    return [{"type": "bot", "text": explanation}]


def _get_history(user_id):
    if user_id not in _chat_history:
        _chat_history[user_id] = []
    return _chat_history[user_id]


def _chat_reply(user_id, user_text=None):
    """Append user_text (if any) to history, call llm.chat(), append response, return text."""
    hist = _get_history(user_id)
    if user_text:
        hist.append({"role": "user", "content": user_text})
    try:
        reply = llm.chat(user_id, hist if hist else None)
    except Exception as e:
        logger.warning(f"Chat LLM error: {e}")
        reply = 'I can sort out study groups, class sections, plans, or chores. Try "chores" or "study CSE310".'
    hist.append({"role": "assistant", "content": reply})
    # Rolling window
    if len(hist) > _MAX_HISTORY:
        _chat_history[user_id] = hist[-_MAX_HISTORY:]
    return reply


def _parse_message(text, user_id, flow=None):
    """Parse user message into intent + args. Returns (messages, needs_veto_reason)."""
    text = text.strip()
    lower = text.lower()

    if lower in ("approve", "confirm", "yes", "ok"):
        return _handle_approve(user_id), False
    if lower in ("veto", "another option", "no"):
        return _handle_veto(user_id), True
    if lower in ("why", "why this plan?", "explain"):
        return _handle_explain(user_id), False

    found = _detect_feature(text, loose=True)
    if found:
        feat, args = found
        if feat in ("study", "class") and not args:
            return [{"type": "bot", "text": f'Which class? Say something like "{feat} CSE310".'}], False
        return _run_feature(feat, args, user_id, flow), False

    return [{"type": "bot", "text": _chat_reply(user_id, text)}], False


_TOPICS = (
    ("chores", r"\bchores?\b|\bdishes\b|\btrash\b|\bvacuum"),
    ("study",  r"\bstud(y|ying)\b|\bstudy group\b"),
    ("class",  r"\bclass(es)?\b|\bsections?\b|\benroll"),
    ("plans",  r"\bplans?\b|\bevents?\b|\bhang ?out\b|\bgo out\b"),
)
_COURSE = re.compile(r"\b([A-Za-z]{2,4})\s*-?\s*(\d{3})\b")


def _detect_feature(text, loose):
    t = text.strip()
    if t.lower().startswith("@squad") or t.lower().startswith("@roomie"):
        t = re.sub(r'^@\w+\s*', '', t)
    low = t.lower()

    for feat, _ in _TOPICS:
        if low == feat or low.startswith(feat + " "):
            return feat, t[len(feat):].strip()

    if not loose:
        return None

    for feat, pattern in _TOPICS:
        if re.search(pattern, low):
            course = _COURSE.search(t)
            return feat, (f"{course.group(1)} {course.group(2)}" if course else "")
    return None


def _extract_user(qs_dict, body=None):
    """Extract user from query string or POST body."""
    user = None
    if qs_dict.get("user"):
        user = qs_dict["user"][0].lower()
    if not user and body and isinstance(body, dict):
        user = (body.get("user") or "").lower()
    if user not in STUDENT_META:
        user = "shreeya"  # fallback
    return user


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path == "/":
            self._serve_file("static/index.html", "text/html")
        elif path == "/api/prefs":
            user = _extract_user(qs)
            self._json_response(prefs.public(user))
        elif path == "/api/state":
            user = _extract_user(qs)
            us = _ustate(user)
            state = negotiator.public_state(us["neg_id"]) if us["neg_id"] else None
            self._json_response({"state": state})
        elif path == "/api/greeting":
            user = _extract_user(qs)
            self._json_response({"text": _chat_reply(user)})
        elif path == "/api/init":
            user = _extract_user(qs)
            greeting = _chat_reply(user)
            self._json_response({"greeting": greeting})
        else:
            super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)
        body = self._read_body()
        user = _extract_user(qs, body)
        flow = body.get("flow") or (qs.get("flow", [None])[0])

        if path == "/api/scenario":
            action = body.get("action", "next")
            value = body.get("value")
            result = scenarios.advance(user, action, value)
            # Step 13 delegates to chores
            if result.get("messages") == "__chores__":
                prefs.reset_chores(user)
                prefs.apply(user)
                msgs = _run_feature("chores", "", user, flow)
                result["messages"] = msgs
            self._json_response(result)

        elif path == "/api/message":
            us = _ustate(user)
            text = body.get("text", "")
            lower = text.strip().lower()
            if us["awaiting_veto_reason"] and lower not in (
                "approve", "confirm", "yes", "ok", "veto", "another option", "no",
                "why", "why this plan?", "explain",
            ) and _detect_feature(text, loose=False) is None:
                msgs = _handle_veto_reason(text, user)
                us["awaiting_veto_reason"] = False
            else:
                msgs, needs_reason = _parse_message(text, user, flow)
                us["awaiting_veto_reason"] = needs_reason
            self._json_response({"messages": msgs})

        elif path == "/api/prefs":
            prefs.save(body, user)
            self._json_response(prefs.public(user))

        elif path == "/api/veto-reason":
            us = _ustate(user)
            reason = body.get("reason", "")
            msgs = _handle_veto_reason(reason, user)
            us["awaiting_veto_reason"] = False
            self._json_response({"messages": msgs})

        else:
            self.send_error(404)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    def _json_response(self, data):
        payload = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(payload))
        self.end_headers()
        self.wfile.write(payload)

    def _serve_file(self, filepath, content_type):
        base = os.path.dirname(os.path.abspath(__file__))
        full = os.path.join(base, filepath)
        try:
            with open(full, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", len(data))
            self.end_headers()
            self.wfile.write(data)
        except FileNotFoundError:
            self.send_error(404, f"{filepath} not found")

    def log_message(self, format, *args):
        logger.info(format % args)


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    logger.info(f"RoomieAgent web UI: http://localhost:{PORT}?user=shreeya")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down.")
        server.server_close()
