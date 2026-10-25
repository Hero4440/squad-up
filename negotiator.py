"""Multi-round negotiation engine: propose → veto → counter → signed.

Max 3 rounds. State stored in-memory per negotiation.
"""

import uuid

# In-memory store. ponytail: dict is fine, no DB needed for hackathon demo.
_negotiations = {}


def create(feature, channel, participants, proposal, solver_fn, solver_args):
    """Start a new negotiation.

    solver_fn: callable to re-run with updated constraints
    solver_args: dict of base args for solver (without constraints)
    """
    neg_id = f"neg_{uuid.uuid4().hex[:8]}"
    neg = {
        "id": neg_id,
        "feature": feature,
        "channel": channel,
        "participants": list(participants),
        "rounds": [{
            "proposal": proposal,
            "approvals": {},
            "vetoes": {},
        }],
        "constraints": [],
        "status": "proposing",
        "solver_fn": solver_fn,
        "solver_args": solver_args,
    }
    _negotiations[neg_id] = neg
    return neg


def get(neg_id):
    return _negotiations.get(neg_id)


def approve(neg_id, student_id):
    """Record approval. Returns updated negotiation."""
    neg = _negotiations.get(neg_id)
    if not neg or neg["status"] != "proposing":
        return neg

    current_round = neg["rounds"][-1]
    current_round["approvals"][student_id] = True

    # Check if all approved
    if all(sid in current_round["approvals"] for sid in neg["participants"]):
        neg["status"] = "signed"

    return neg


def veto(neg_id, student_id, reason="", public_reason="Not available at that time"):
    """Record veto, add constraint, re-propose if rounds left.

    reason: private (stored but never shown in channel)
    public_reason: safe message for channel
    """
    neg = _negotiations.get(neg_id)
    if not neg or neg["status"] != "proposing":
        return neg

    current_round = neg["rounds"][-1]
    current_round["vetoes"][student_id] = {
        "private_reason": reason,
        "public_reason": public_reason,
    }

    round_num = len(neg["rounds"])
    if round_num >= 3:
        neg["status"] = "failed"
        return neg

    # Add constraint based on feature type
    proposal = current_round["proposal"]
    constraint = _extract_constraint(neg["feature"], proposal, student_id)
    if constraint:
        neg["constraints"].append(constraint)

    # Re-solve with accumulated constraints
    solver_fn = neg["solver_fn"]
    solver_args = dict(neg["solver_args"])
    solver_args["constraints"] = neg["constraints"]
    new_proposal = solver_fn(**solver_args)

    # chores come back as {"assignments": ...} rather than {"proposal": ...}
    if new_proposal.get("proposal") is None and new_proposal.get("assignments") is None:
        neg["status"] = "failed"
        return neg

    neg["rounds"].append({
        "proposal": new_proposal,
        "approvals": {},
        "vetoes": {},
    })
    neg["status"] = "proposing"

    return neg


def _extract_constraint(feature, proposal, student_id):
    """Turn a veto into a solver constraint."""
    if feature == "class":
        sec = proposal.get("proposal", {})
        return sec.get("section") if isinstance(sec, dict) else None
    elif feature == "study":
        return proposal.get("proposal")  # slot string
    elif feature == "plans":
        event = proposal.get("event", {})
        return event.get("title")
    elif feature == "chores":
        # For chores, constraint is (student_id, chore) — needs user input
        # Default: exclude their worst chore from current assignment
        student_chores = proposal.get("student_chores", {})
        assigned = student_chores.get(student_id, [])
        return (student_id, assigned[0]) if assigned else None
    return None


def current_proposal(neg_id):
    """Get the latest proposal from a negotiation."""
    neg = _negotiations.get(neg_id)
    if not neg or not neg["rounds"]:
        return None
    return neg["rounds"][-1]["proposal"]


def current_round_num(neg_id):
    neg = _negotiations.get(neg_id)
    return len(neg["rounds"]) if neg else 0


def public_state(neg_id):
    """Negotiation state safe for channel display (no private reasons)."""
    neg = _negotiations.get(neg_id)
    if not neg:
        return None
    rounds = []
    for r in neg["rounds"]:
        rounds.append({
            "proposal": r["proposal"],
            "approvals": list(r["approvals"].keys()),
            "vetoes": {
                sid: v["public_reason"]
                for sid, v in r["vetoes"].items()
            },
        })
    return {
        "id": neg["id"],
        "feature": neg["feature"],
        "participants": neg["participants"],
        "rounds": rounds,
        "status": neg["status"],
        "round_num": len(neg["rounds"]),
    }
