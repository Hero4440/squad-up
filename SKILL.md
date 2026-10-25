# Squad Up — Cubbie Skill Definition

## Skill Name
Squad Up

## Track
Track 2 (Agent-to-Agent Coordination) + Track 3 (Group Chat Assistant)

## Description
Slack bot where each student's AI agent (Claude-powered) negotiates with friends' agents in group channels. Agents propose, veto, and counter-offer across 4 features: class section coordination, study group scheduling, event planning, and chore splitting.

## Platform
Slack (Socket Mode)

## Agent Architecture
- Each student has a personal AI agent backed by Claude Haiku
- Agents reason about the student's full profile but only share allowlisted fields
- Privacy enforced at the code level — agents never leak schedules, reasons, or private notes
- Multi-round negotiation: propose → veto → counter-offer → signed (max 3 rounds)

## Features

### 1. Class Section Coordination (`/squad class CSE310`)
Fetches open sections from ASU API, agents check schedule conflicts, proposes section with most students available.

### 2. Study Group Scheduling (`/squad study CSE310`)
Agents extract free slots, solver intersects availability, suggests location by campus.

### 3. Event Squad (`/squad plans`)
Fetches upcoming ASU events, agents check conflicts (binary), groups by campus for carpool.

### 4. Chore Split (`/squad chores`)
Agents share chore preferences (1-5), solver uses maximin fairness, assigns to maximize minimum happiness.

## Privacy Model
Allowlist-based redaction per feature. Agents never share: full schedules, private notes, reasons for conflicts, personality details.

## Tech Stack
- Python 3.10+
- slack_bolt (Socket Mode)
- anthropic (Claude Haiku)
- ASU public APIs (classes, events)

## Demo Flow
1. `/squad study CSE310` in Slack channel
2. Bot shows privacy consent → user clicks Start
3. Agents post availability messages
4. Solver proposes time + location
5. Users vote with Approve/Veto buttons
6. Veto → private DM for reason → safe public message → re-propose
7. All approve → Signed!

## Campus Bestie Integration
Reuses `asu_search.py` (ASU API client) and extends `privacy.py` from Campus Bestie (Track 1).
