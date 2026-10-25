"""Tests for solvers + negotiation — run without Slack or API keys.

    python -m pytest tests/test_solvers.py -v
    # or just:
    python tests/test_solvers.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents import load_profiles, get_free_slots_hourly, students_in_course, get_profile
from solvers import solve_study, solve_chores, solve_plans, solve_class
from privacy import redact, ALLOWED
import negotiator


def setup():
    load_profiles()


def test_profiles_load():
    setup()
    profiles = students_in_course("CSE", "310")
    assert len(profiles) >= 2, f"Expected >=2 students in CSE310, got {len(profiles)}"
    assert "maya" in profiles
    assert "leo" in profiles


def test_free_slots():
    setup()
    slots = get_free_slots_hourly("maya")
    assert len(slots) > 0, "Maya should have free slots"
    # Maya has CSE310 Mon 9:00-10:15, so Mon 9:00-10:00 should NOT be free
    assert "Mon 9:00-10:00" not in slots, "Mon 9-10 should be busy for Maya"
    # Mon afternoon should be free
    assert any("Mon 15:" in s or "Mon 14:" in s for s in slots), "Maya should be free Mon afternoon"


def test_solve_study():
    setup()
    result = solve_study("CSE310", ["maya", "jordan", "leo"])
    assert result["proposal"] is not None, "Should find a study slot"
    assert result["location"], "Should suggest a location"
    assert "/" in result["attendance"], "Should have attendance ratio"


def test_solve_study_with_constraints():
    setup()
    result1 = solve_study("CSE310", ["maya", "jordan", "leo"])
    slot1 = result1["proposal"]
    # Constrain that slot, should get a different one
    result2 = solve_study("CSE310", ["maya", "jordan", "leo"], constraints=[slot1])
    if result2["proposal"] is not None:
        assert result2["proposal"] != slot1, "Should propose different slot after constraint"


def test_solve_chores():
    setup()
    result = solve_chores(["maya", "jordan", "leo"])
    assert result["assignments"], "Should assign chores"
    assert result["min_happiness"] > 0, "Min happiness should be positive"
    # All chores assigned
    assigned_chores = set(result["assignments"].keys())
    assert "dishes" in assigned_chores
    assert "bathroom" in assigned_chores
    # Leo has bathroom pref 5, should get it
    assert result["assignments"]["bathroom"] == "leo", \
        f"Leo should get bathroom (pref 5), got {result['assignments']['bathroom']}"


def test_solve_chores_with_constraints():
    setup()
    # Constrain Leo from bathroom
    result = solve_chores(["maya", "jordan", "leo"], constraints=[("leo", "bathroom")])
    assert result["assignments"]["bathroom"] != "leo", "Leo should not get bathroom after constraint"


def test_solve_plans():
    setup()
    event = {"title": "Fall Career Fair", "date": "Nov 1",
             "time": "10am-3pm", "location": "Tempe campus"}
    result = solve_plans(event, ["maya", "jordan", "leo"])
    assert len(result["who_can_go"]) > 0, "Someone should be able to go"
    assert result["carpool_groups"], "Should have carpool groups"


def test_solve_class():
    setup()
    sections = [
        {"section": "1001", "days": "MW", "time": "9:00-10:15", "seats_open": 50,
         "location": "TEMPE", "course": "CSE 310"},
        {"section": "1002", "days": "MW", "time": "2:00-3:15", "seats_open": 30,
         "location": "TEMPE", "course": "CSE 310"},
    ]
    result = solve_class("CSE", "310", sections, ["maya", "jordan", "leo"])
    assert result["proposal"] is not None, "Should propose a section"
    assert int(result["attendance"].split("/")[0]) > 0, "Someone should be able to attend"


def test_privacy_redaction():
    setup()
    profile = get_profile("maya")
    for feature, allowed in ALLOWED.items():
        safe = redact(profile, feature)
        assert "private_notes" not in safe, f"Leaked private_notes in {feature}"
        assert "schedule" not in safe, f"Leaked schedule in {feature}"
        assert "personality" not in safe, f"Leaked personality in {feature}"
        for key in safe:
            assert key in allowed, f"Field {key} not in allowlist for {feature}"


def test_negotiation_flow():
    setup()
    proposal = solve_study("CSE310", ["maya", "jordan", "leo"])
    neg = negotiator.create(
        "study", "C_TEST", ["maya", "jordan", "leo"], proposal,
        solve_study, {"course_key": "CSE310", "participants": ["maya", "jordan", "leo"]},
    )
    assert neg["status"] == "proposing"

    # Approve two
    negotiator.approve(neg["id"], "maya")
    negotiator.approve(neg["id"], "jordan")
    state = negotiator.get(neg["id"])
    assert state["status"] == "proposing", "Should still be proposing with 2/3 approvals"

    # Approve third → signed
    negotiator.approve(neg["id"], "leo")
    state = negotiator.get(neg["id"])
    assert state["status"] == "signed", "Should be signed after all approve"


def test_negotiation_veto():
    setup()
    proposal = solve_study("CSE310", ["maya", "jordan", "leo"])
    neg = negotiator.create(
        "study", "C_TEST", ["maya", "jordan", "leo"], proposal,
        solve_study, {"course_key": "CSE310", "participants": ["maya", "jordan", "leo"]},
    )

    # Veto
    neg = negotiator.veto(neg["id"], "maya", "I work then", "Not available")
    assert len(neg["rounds"]) == 2, "Should have round 2 after veto"
    assert neg["status"] == "proposing"

    # Public state should not contain private reason
    pub = negotiator.public_state(neg["id"])
    for r in pub["rounds"]:
        for sid, reason in r["vetoes"].items():
            assert "work" not in reason.lower(), f"Leaked private reason: {reason}"


def test_negotiation_max_rounds():
    setup()
    proposal = solve_study("CSE310", ["maya", "jordan", "leo"])
    neg = negotiator.create(
        "study", "C_TEST", ["maya", "jordan", "leo"], proposal,
        solve_study, {"course_key": "CSE310", "participants": ["maya", "jordan", "leo"]},
    )

    # 3 vetoes → failed
    negotiator.veto(neg["id"], "maya", "reason1", "nope")
    negotiator.veto(neg["id"], "jordan", "reason2", "nope")
    neg = negotiator.veto(neg["id"], "leo", "reason3", "nope")
    assert neg["status"] == "failed", "Should fail after 3 rounds"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {t.__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
