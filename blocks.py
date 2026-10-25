"""Slack Block Kit message builders for Squad Up."""


def privacy_consent(feature, shared_fields, hidden_fields):
    """Ephemeral message asking user to confirm what gets shared."""
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*Squad Up — {feature.title()}*\n\n"
                    f":white_check_mark: *I'll share:* {', '.join(sorted(shared_fields))}\n"
                    f":no_entry_sign: *I won't share:* {', '.join(sorted(hidden_fields))}"
                ),
            },
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Start"},
                    "style": "primary",
                    "action_id": "consent_start",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Cancel"},
                    "action_id": "consent_cancel",
                },
            ],
        },
    ]


def proposal_message(feature, round_num, agent_messages, proposal_text, participants, neg_id):
    """Channel message with proposal + approve/veto buttons per participant."""
    emoji_map = {"class": ":school:", "study": ":books:", "plans": ":calendar:", "chores": ":broom:"}
    emoji = emoji_map.get(feature, ":sparkles:")

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"{feature.title()} — Round {round_num}"},
        },
    ]

    # Agent messages
    for sid, msg in agent_messages.items():
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*{sid}'s agent:* \"{msg}\""},
        })

    blocks.append({"type": "divider"})

    # Proposal
    blocks.append({
        "type": "section",
        "text": {"type": "mrkdwn", "text": f"{emoji} *Proposal:* {proposal_text}"},
    })

    # Approve/Veto buttons
    for sid in participants:
        blocks.append({
            "type": "actions",
            "block_id": f"vote_{neg_id}_{sid}",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Approve"},
                    "style": "primary",
                    "action_id": f"approve_{neg_id}",
                    "value": sid,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Veto"},
                    "style": "danger",
                    "action_id": f"veto_{neg_id}",
                    "value": sid,
                },
            ],
        })

    return blocks


def outcome_signed(feature, summary):
    """Signed agreement message."""
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f":white_check_mark: *Signed!* {feature.title()} agreed.\n\n{summary}",
            },
        },
    ]


def outcome_failed(feature, summary):
    """Failed negotiation message."""
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f":x: *No agreement* on {feature.title()} after 3 rounds.\n\n"
                    f"{summary}\n\n"
                    "Consider meeting in person to discuss."
                ),
            },
        },
    ]


def veto_dm():
    """DM asking vetoing user for their private reason."""
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "You vetoed the proposal. Can you share *privately* why?\n"
                    "This stays between you and your agent — only a safe summary goes to the group."
                ),
            },
        },
        {
            "type": "input",
            "block_id": "veto_reason_block",
            "element": {
                "type": "plain_text_input",
                "action_id": "veto_reason_input",
                "placeholder": {"type": "plain_text", "text": "e.g. I work at that time"},
            },
            "label": {"type": "plain_text", "text": "Reason (private)"},
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Submit"},
                    "style": "primary",
                    "action_id": "veto_reason_submit",
                },
            ],
        },
    ]
