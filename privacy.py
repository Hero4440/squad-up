"""Allowlist-based profile redaction for Squad Up features."""

ALLOWED = {
    "class":  {"id", "name", "campus", "courses"},
    "study":  {"id", "name", "campus", "available_slots"},
    "plans":  {"id", "name", "campus", "interested", "has_conflict"},
    "chores": {"id", "name", "chore_preferences"},
}


def redact(profile, feature):
    """Return only allowed fields for a feature."""
    allowed = ALLOWED.get(feature)
    if not allowed:
        raise ValueError(f"Unknown feature: {feature}")
    return {k: v for k, v in profile.items() if k in allowed}


def redact_list(profiles, feature):
    return [redact(p, feature) for p in profiles]


if __name__ == "__main__":
    full = {
        "id": "shreeya", "name": "Shreeya", "campus": "TEMPE",
        "courses": [{"subject": "CSE", "number": "310"}],
        "available_slots": ["Mon 3-5pm"],
        "schedule": {"Mon": ["9:00-10:15 CSE310"]},
        "private_notes": "Works at Starbucks",
        "chore_preferences": {"dishes": 3},
    }
    for feat in ALLOWED:
        safe = redact(full, feat)
        assert "schedule" not in safe, f"Leaked schedule in {feat}"
        assert "private_notes" not in safe, f"Leaked private_notes in {feat}"
    print("All privacy checks passed.")
