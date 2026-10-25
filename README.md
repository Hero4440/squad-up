# RoomieAgent

AI-powered roommate coordination app for ASU students. Chat naturally with RoomieAgent to split chores, schedule study groups, pick class sections, and plan events — all while keeping your private info safe.

Built for the Cubbie Hackathon. Tracks 2 (Agent-to-Agent Coordination) + 3 (Group Chat Assistant).

## What It Does

You open the chat as yourself (Shreeya, Rishi, Tejas, or Arjun). RoomieAgent greets you and you can talk freely — ask questions, get suggestions, or trigger a feature by name.

When you trigger a feature, each roommate's personal AI agent negotiates on their behalf. Agents only share what's on their allowlist — schedules, private notes, and personal reasons stay hidden.

### Features

| Trigger | What happens |
|---------|-------------|
| `chores` | Splits cleaning, dishes, dusting, cooking using maximin fairness |
| `study CSE310` | Finds a study time + location that works for everyone in the course |
| `class CSE310` | Picks the best section from live ASU class data |
| `plans` | Coordinates event attendance + carpool groups by campus |

### How Negotiation Works

```
You: "chores"
  → RoomieAgent asks your chore preferences (tap once per chore)
  → Solver assigns chores to maximize the minimum happiness
  → Other roommates' AI agents comment on the proposal
  → You see a proposal card: approve or veto
  → Veto? Give a private reason → safe public version is shared → re-propose (max 3 rounds)
  → All approve? Locked in.
```

### Privacy

Each feature has a strict allowlist. Agents **never** leak:
- Full schedules
- Private notes (work, health, personal circumstances)
- Real reasons for vetoes (only AI-sanitized summaries)

## Demo Profiles

| Student | Campus | Courses | Style |
|---------|--------|---------|-------|
| Shreeya | Tempe | CSE310, CSE240, PHY121 | Organized, morning person |
| Rishi | Downtown | CSE310, CSE240, ENG101 | Social, night owl |
| Tejas | Tempe | CSE310, MAT267 | Chill, flexible |
| Arjun | Tempe | CSE360, CSE240, MAT243 | Neat, early riser |

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Set your API key

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

Or create a `.env` file:

```
ANTHROPIC_API_KEY=sk-ant-...
```

### 3. Run

```bash
python3 web.py
```

Open [http://localhost:8888?user=shreeya](http://localhost:8888?user=shreeya)

Switch users by changing `?user=rishi`, `?user=tejas`, or `?user=arjun`.

### 4. Test (no API key needed)

```bash
python3 tests/test_solvers.py
```

## Deploy

Works on any platform that runs Python. Example with Render:

1. Push to GitHub
2. Render → New Web Service → connect repo
3. Build command: `pip install -r requirements.txt`
4. Start command: `python web.py`
5. Add environment variable: `ANTHROPIC_API_KEY`

## Architecture

```
web.py           ← HTTP server, chat API, feature routing
llm.py           ← Anthropic Claude API — free-form chat + agent reasoning
agents.py        ← Profile loading, schedule parsing, free slot extraction
solvers.py       ← 4 solvers (class, study, plans, chores)
negotiator.py    ← Multi-round propose/veto/counter engine
prefs.py         ← Per-user preferences (chores, vibe, campus, avatar)
privacy.py       ← Allowlist-based redaction per feature
asu_search.py    ← ASU public API client (classes, events, news)
scenarios.py     ← Scripted demo flow (legacy, not used in chat mode)
static/index.html ← Single-page chat UI (WhatsApp-style)
profiles/        ← Student profiles + saved preferences
```

## Tech Stack

- **Backend:** Python stdlib HTTP server (no framework)
- **LLM:** Claude Haiku via Anthropic API
- **Frontend:** Vanilla HTML/CSS/JS — single file, no build step
- **Data:** ASU public class/event APIs, local JSON profiles
