# Squad Up

Slack bot for multi-agent negotiation between ASU students. Each student's AI agent (Claude Haiku) negotiates with friends' agents in group channels.

**Tracks:** 2 (Agent-to-Agent Coordination) + 3 (Group Chat Assistant)

## Features

| Command | What it does |
|---------|-------------|
| `/squad class CSE310` | Coordinate class sections — find one that works for everyone |
| `/squad study CSE310` | Schedule study group — find time + location |
| `/squad plans` | Plan event attendance — who can go, carpool groups |
| `/squad chores` | Split household chores — maximin fairness |

## How It Works

```
User: /squad study CSE310
  ↓
Bot: Privacy consent (ephemeral) → [Start] [Cancel]
  ↓
Agents: Each agent shares only allowlisted info
  ↓
Solver: Finds best option (intersection/optimization)
  ↓
Bot: Posts proposal with [Approve] [Veto] per person
  ↓
If veto: Private DM → safe public reason → re-propose (max 3 rounds)
If all approve: ✅ Signed!
```

## Privacy

Allowlist-based redaction per feature. Agents **never** share:
- Full schedules
- Private notes (work, health, personal)
- Reasons for vetoes (only safe summaries)

## Setup

### 1. Create Slack App

Go to https://api.slack.com/apps → Create New App → From Manifest:

```yaml
display_information:
  name: Squad Up
  description: AI agent negotiation for student groups
features:
  bot_user:
    display_name: Squad Up
    always_online: true
  slash_commands:
    - command: /squad
      description: Start a group negotiation
      usage_hint: "<class|study|plans|chores> [args]"
  interactivity:
    is_enabled: true
oauth_config:
  scopes:
    bot:
      - commands
      - chat:write
      - im:write
      - users:read
settings:
  socket_mode_enabled: true
```

### 2. Install & Configure

```bash
# Install to workspace, then copy tokens
cp .env.example .env
# Edit .env with your tokens:
#   SLACK_BOT_TOKEN=xoxb-...
#   SLACK_APP_TOKEN=xapp-...
#   ANTHROPIC_API_KEY=sk-ant-...
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Run

```bash
python3 bot.py
```

### 5. Test (no Slack/API needed)

```bash
python3 tests/test_solvers.py
```

## Architecture

```
bot.py          ← Slack Bolt app, slash commands, buttons, Socket Mode
agents.py       ← Profile loading, schedule parsing, free slot extraction
solvers.py      ← 4 solvers (class, study, plans, chores)
negotiator.py   ← Multi-round negotiation engine (propose/veto/counter)
llm.py          ← Claude Haiku wrapper for agent reasoning
privacy.py      ← Allowlist redaction per feature
asu_search.py   ← ASU public API client (classes, events, news, people)
blocks.py       ← Slack Block Kit message builders
profiles/       ← Sample student profiles (Maya, Jordan, Leo)
```

## Demo Profiles

| Student | Campus | Courses | Personality |
|---------|--------|---------|-------------|
| Maya Chen | Tempe | CSE310, CSE240, PHY121 | Organized, prefers mornings |
| Jordan Rivera | Downtown | CSE310, CSE240, ENG101 | Social, night owl |
| Leo Nguyen | Tempe | CSE310, MAT267 | Chill, flexible |

## Extending

To add a student: edit `profiles/students.json` and update their `slack_id` to match their real Slack user ID.

To add a feature: add a solver in `solvers.py`, a privacy allowlist in `privacy.py`, and wire it into `bot.py`.
