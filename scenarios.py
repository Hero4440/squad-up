"""Squad Up — multi-chat scenario engine.

Three conversations, each with its own step-based flow.
State is in-memory; server restart = fresh demo.
"""

import random

# ---------------------------------------------------------------------------
# Roommate preference questions (housing steps 3-7)
# ---------------------------------------------------------------------------
ROOMMATE_QUESTIONS = [
    {
        "key": "sleep",
        "title": "Sleep schedule",
        "subtitle": "When do you usually sleep?",
        "options": ["Early bird (10pm-6am)", "Normal (11pm-7am)", "Night owl (1am-9am)"],
    },
    {
        "key": "diet",
        "title": "Kitchen & diet",
        "subtitle": "Any food preferences?",
        "options": ["No restrictions", "Vegetarian", "Vegan", "Halal"],
    },
    {
        "key": "budget",
        "title": "Monthly budget",
        "subtitle": "What's your range for rent + utilities?",
        "options": ["$500-700", "$700-900", "$900-1100", "$1100+"],
    },
    {
        "key": "smoking",
        "title": "Smoking & vaping",
        "subtitle": "Your preference?",
        "options": ["No smoking/vaping", "Outside only", "No preference"],
    },
    {
        "key": "room",
        "title": "Room setup",
        "subtitle": "How do you keep your space?",
        "options": ["Very neat", "Mostly tidy", "Organized chaos", "Whatever works"],
    },
]

# ---------------------------------------------------------------------------
# Scripted matches (housing)
# ---------------------------------------------------------------------------
MATCHES = {
    "shreeya": {
        "partner": "arjun", "score": 4, "of": 5,
        "alignment": [
            {"label": "Sleep schedule", "match": True, "detail": "Both early birds"},
            {"label": "Budget range", "match": True, "detail": "$700-900"},
            {"label": "Room tidiness", "match": True, "detail": "Both very neat"},
            {"label": "Kitchen", "match": False, "detail": "Different diet prefs"},
            {"label": "No smoking", "match": True, "detail": "Both non-smokers"},
        ],
        "flags": [],
    },
    "arjun": {
        "partner": "shreeya", "score": 4, "of": 5,
        "alignment": [
            {"label": "Sleep schedule", "match": True, "detail": "Both early birds"},
            {"label": "Budget range", "match": True, "detail": "$700-900"},
            {"label": "Room tidiness", "match": True, "detail": "Both very neat"},
            {"label": "Kitchen", "match": False, "detail": "Different diet prefs"},
            {"label": "No smoking", "match": True, "detail": "Both non-smokers"},
        ],
        "flags": [],
    },
    "rishi": {
        "partner": "tejas", "score": 4, "of": 5,
        "alignment": [
            {"label": "Sleep schedule", "match": True, "detail": "Both night owls"},
            {"label": "Budget range", "match": True, "detail": "$500-700"},
            {"label": "Room tidiness", "match": False, "detail": "Different standards"},
            {"label": "Kitchen", "match": True, "detail": "No restrictions"},
            {"label": "No smoking", "match": True, "detail": "Both non-smokers"},
        ],
        "flags": [],
    },
    "tejas": {
        "partner": "rishi", "score": 4, "of": 5,
        "alignment": [
            {"label": "Sleep schedule", "match": True, "detail": "Both night owls"},
            {"label": "Budget range", "match": True, "detail": "$500-700"},
            {"label": "Room tidiness", "match": False, "detail": "Different standards"},
            {"label": "Kitchen", "match": True, "detail": "No restrictions"},
            {"label": "No smoking", "match": True, "detail": "Both non-smokers"},
        ],
        "flags": [],
    },
    # Default match for "you" and anyone not listed
    "you": {
        "partner": "shreeya", "score": 4, "of": 5,
        "alignment": [
            {"label": "Sleep schedule", "match": True, "detail": "Both night owls"},
            {"label": "Budget range", "match": True, "detail": "$700-900"},
            {"label": "Room tidiness", "match": True, "detail": "Both mostly tidy"},
            {"label": "Kitchen", "match": False, "detail": "Different diet prefs"},
            {"label": "No smoking", "match": True, "detail": "Both non-smokers"},
        ],
        "flags": [],
    },
}

_PARTNER_NAMES = {
    "shreeya": "Arjun", "arjun": "Shreeya",
    "rishi": "Tejas", "tejas": "Rishi",
    "you": "Shreeya",
}

_GROUP_INTROS = {
    "shreeya": [{"type": "bot", "text": "Hey everyone! Looking for Spring 2027 housing near Tempe campus. I'm organized, early bird, love morning study sessions \u2600\ufe0f"}],
    "rishi":   [{"type": "bot", "text": "Yo! Need a roommate for Spring 2027. Downtown campus, night owl, into hackathons and basketball \U0001F3C0"}],
    "tejas":   [{"type": "bot", "text": "Hey! Chill guy looking for Spring 2027 housing. Tempe campus, flexible schedule, down for whatever \U0001F3AE"}],
    "arjun":   [{"type": "bot", "text": "Hi all! Looking for a roommate near Tempe for Spring 2027. Early riser, keep things neat, into morning runs \U0001F3C3"}],
    "priya":   [{"type": "bot", "text": "Hey! Priya here \u2014 CS major, Tempe campus. Looking for a clean, quiet place. I cook a lot so kitchen matters to me \U0001F373"}],
}

# ---------------------------------------------------------------------------
# Chat list metadata
# ---------------------------------------------------------------------------
CHAT_LIST = [
    {
        "id": "squadup",
        "title": "Squad Up",
        "subtitle": "Your AI assistant",
        "preview": "Hey! I can help with housing, chores, plans\u2026",
        "time": "3:00 PM",
        "unread": 1,
        "color": "#06cf9c",
        "emoji": "\U0001F916",
    },
    {
        "id": "housing",
        "title": "ASU Housing \U0001F335",
        "subtitle": "Spring 2027 Roommate Matching",
        "preview": "RoomieAgent: Ready to find your roommate?",
        "time": "2:30 PM",
        "unread": 3,
        "color": "#8C1D40",
        "emoji": "\U0001F335",
    },
    {
        "id": "friends",
        "title": "ASU Friends \U0001F389",
        "subtitle": "Weekend Plans",
        "preview": "Tejas: Anyone down for something fun?",
        "time": "1:15 PM",
        "unread": 5,
        "color": "#ff9800",
        "emoji": "\U0001F389",
    },
    {
        "id": "house",
        "title": "Our Place \U0001F3E1",
        "subtitle": "ASU 2027 Household",
        "preview": "Arjun: We need to figure out chores",
        "time": "11:40 AM",
        "unread": 2,
        "color": "#00bcd4",
        "emoji": "\U0001F3E1",
    },
]

# ---------------------------------------------------------------------------
# Per-user state
# ---------------------------------------------------------------------------
_state = {}


def _get(user):
    if user not in _state:
        _state[user] = {
            "current_chat": None,
            "chats": {
                "squadup": {"step": 0},
                "housing": {"step": 0, "prefs": {}, "revealed": False},
                "friends": {"step": 0},
                "house":   {"step": 0},
            },
        }
    return _state[user]


def _partner_name(user):
    return _PARTNER_NAMES.get(user, "Shreeya")


# ---------------------------------------------------------------------------
# Top-level entry points
# ---------------------------------------------------------------------------

def current(user):
    """Return current state. Chat list when no active chat, otherwise chat's current step."""
    st = _get(user)
    if st["current_chat"] is None:
        return _chat_list_response()
    return _dispatch(user, st["current_chat"])


def advance(user, action, value=None):
    """Advance scenario based on action."""
    st = _get(user)

    if action == "enter_chat":
        chat_id = value
        if chat_id in st["chats"]:
            st["current_chat"] = chat_id
            return _dispatch(user, chat_id)
        return _chat_list_response()

    if action == "go_back":
        st["current_chat"] = None
        return _chat_list_response()

    # Forward to active chat's handler
    if st["current_chat"] == "squadup":
        return _advance_squadup(user, action, value)
    elif st["current_chat"] == "housing":
        return _advance_housing(user, action, value)
    elif st["current_chat"] == "friends":
        return _advance_friends(user, action, value)
    elif st["current_chat"] == "house":
        return _advance_house(user, action, value)

    return _chat_list_response()


def go_back(user):
    """Return to chat list."""
    st = _get(user)
    st["current_chat"] = None
    return _chat_list_response()


def _chat_list_response():
    return {
        "messages": [{"type": "chat_list", "conversations": CHAT_LIST}],
        "ui_patch": {"header_title": "Squad Up", "header_subtitle": "Your agents talk so you don't have to", "mode": "home"},
    }


def _dispatch(user, chat_id):
    """Route to correct chat's current step."""
    if chat_id == "squadup":
        return _squadup_step(user)
    elif chat_id == "housing":
        return _housing_step(user)
    elif chat_id == "friends":
        return _friends_step(user)
    elif chat_id == "house":
        return _house_step(user)
    return _chat_list_response()


# ===================================================================
# SQUAD UP 1-on-1 BOT CHAT (freeform after intro)
# ===================================================================

def _squadup_step(user):
    """Intro message, then hand off to freeform chat mode."""
    return {
        "messages": [
            {"type": "bot", "text": "Hey! I\u2019m Squad Up \u2014 your AI assistant for all things ASU housing."},
            {"type": "bot", "text": "I can help with:\n\U0001F3E0 Roommate matching\n\U0001F9F9 Chore splitting\n\U0001F389 Event planning\n\U0001F4DA Study groups\n\nJust type what you need!"},
        ],
        "ui_patch": {"header_title": "Squad Up", "header_subtitle": "AI assistant", "mode": "squadup"},
        "freeform": True,
    }


def _advance_squadup(user, action, value):
    return _squadup_step(user)


# ===================================================================
# HOUSING FLOW (13 steps — existing roommate matching)
# ===================================================================

def _housing_step(user):
    st = _get(user)
    step = st["chats"]["housing"]["step"]

    if step == 0:   return _h_welcome(user)
    elif step == 1:  return _h_group_chat(user)
    elif step == 2:  return _h_transition(user)
    elif step == 3:  return _h_private_dm(user)
    elif 4 <= step <= 8: return _h_preference(user, step - 4)
    elif step == 9:  return _h_saved(user)
    elif step == 10: return _h_match_found(user)
    elif step == 11: return _h_match_detail(user)
    elif step == 12: return _h_confirmed(user)
    else:
        partner = _partner_name(user)
        return {
            "messages": [
                {"type": "bot", "text": f"You're all matched up with {partner}! \U0001F389 Head over to **Our Place** to set up your house."},
            ],
            "ui_patch": {"header_title": "ASU Spring 2027 Housing \U0001F335", "header_subtitle": "Matching complete", "mode": "group"},
        }


def _advance_housing(user, action, value):
    st = _get(user)
    hs = st["chats"]["housing"]
    step = hs["step"]

    if 4 <= step <= 8 and action == "pick" and value is not None:
        q = ROOMMATE_QUESTIONS[step - 4]
        hs["prefs"][q["key"]] = value

    if step == 10 and action == "show_more":
        hs["revealed"] = True
        hs["step"] = 11
        return _housing_step(user)
    if step == 10 and action == "connect":
        hs["step"] = 12
        return _housing_step(user)
    if step == 11 and action == "connect":
        hs["step"] = 12
        return _housing_step(user)

    hs["step"] = min(step + 1, 13)  # cap at 13 (complete)
    return _housing_step(user)


def _h_welcome(user):
    """Welcome message before entering the group chat."""
    return {
        "messages": [
            {"type": "bot", "text": "Welcome to ASU Spring 2027 Housing! \U0001F335"},
            {"type": "bot", "text": "I\u2019m RoomieAgent \u2014 I\u2019ll help you find the perfect roommate based on lifestyle compatibility."},
            {
                "type": "notice_card",
                "title": "\U0001F3E0 How it works",
                "body": "1. Join the housing group chat\n2. Answer 5 quick private questions\n3. Get matched with a compatible roommate\n4. Set up your house together",
                "cta": "Enter group chat",
                "action": "next",
            },
        ],
        "ui_patch": {"header_title": "ASU Housing \U0001F335", "header_subtitle": "RoomieAgent", "mode": "housing_intro"},
    }


def _h_group_chat(user):
    msgs = [{"type": "system", "text": "ASU Spring 2027 Housing \U0001F335"}]
    shown = 0
    for uid in ["shreeya", "rishi", "tejas", "arjun", "priya"]:
        if uid != user and shown < 2:
            for m in _GROUP_INTROS.get(uid, []):
                msgs.append({**m, "sender": uid})
            shown += 1
    msgs.append({"type": "bot", "text": "Hey everyone! \U0001F44B I'm RoomieAgent \u2014 your AI roommate matchmaker."})
    msgs.append({"type": "bot", "text": "Here\u2019s how it works:\n1\ufe0f\u20e3 I\u2019ll ask you a few private questions about your lifestyle\n2\ufe0f\u20e3 Match you with compatible students\n3\ufe0f\u20e3 Set up your house group & help split chores"})
    msgs.append({"type": "bot", "text": "Everything you share stays private \u2014 I only reveal compatibility scores, never your actual answers."})
    msgs.append({
        "type": "notice_card",
        "title": "\U0001F3E0 Ready?",
        "body": "Tap below to start the matching process. Takes about 2 minutes.",
        "cta": "Start Roommate Matching",
        "action": "start",
    })
    return {
        "messages": msgs,
        "ui_patch": {"header_title": "ASU Spring 2027 Housing \U0001F335", "header_subtitle": "34 members", "mode": "group"},
    }


def _h_transition(user):
    return {
        "messages": [
            {"type": "bot", "text": "I\u2019ve sent you a private message! Let\u2019s find your perfect roommate match \U0001F512"},
        ],
        "ui_patch": {"header_title": "RoomieAgent", "header_subtitle": "Private chat", "mode": "private"},
    }


def _h_private_dm(user):
    return {
        "messages": [
            {"type": "bot", "text": "Hey! This is just between us. I\u2019ll ask you 5 quick questions about your lifestyle preferences."},
            {"type": "bot", "text": "Your answers stay private \u2014 I only share compatibility scores, never your actual responses."},
            {"type": "notice_card", "title": "\U0001F512 Privacy first", "body": "Your preferences are encrypted and never shared with other users. Only compatibility scores are visible.", "cta": "Yes, let\u2019s go!", "action": "consent"},
        ],
        "ui_patch": {"header_title": "RoomieAgent", "header_subtitle": "Private chat", "mode": "private"},
    }


def _h_preference(user, q_index):
    q = ROOMMATE_QUESTIONS[q_index]
    progress = f"Question {q_index + 1} of {len(ROOMMATE_QUESTIONS)}"
    return {
        "messages": [
            {"type": "system", "text": progress},
            {"type": "pref_card", "topic": q["key"], "title": q["title"], "subtitle": q["subtitle"],
             "items": [{"key": opt, "label": opt} for opt in q["options"]]},
        ],
        "ui_patch": {"header_title": "RoomieAgent", "header_subtitle": f"Private chat \u00b7 {progress}", "mode": "private"},
    }


def _h_saved(user):
    return {
        "messages": [
            {"type": "bot", "text": "All saved! Analyzing compatibility with other students... \U0001F50D"},
            {"type": "system", "text": "Matching in progress..."},
        ],
        "ui_patch": {"header_title": "RoomieAgent", "header_subtitle": "Finding your match...", "mode": "private"},
    }


def _h_match_found(user):
    match = MATCHES.get(user, MATCHES["you"])
    return {
        "messages": [
            {"type": "bot", "text": "Found a great match for you! \U0001F389"},
            {
                "type": "match_card",
                "score": match["score"], "of": match["of"],
                "alignment": match["alignment"], "flags": match["flags"],
                "actions": [
                    {"label": "Show more", "action": "show_more"},
                    {"label": "Connect", "action": "connect"},
                    {"label": "Pass", "action": "pass"},
                ],
                "revealed": False, "partner_name": None,
            },
        ],
        "ui_patch": {"header_title": "RoomieAgent", "header_subtitle": "Match found!", "mode": "private"},
    }


def _h_match_detail(user):
    match = MATCHES.get(user, MATCHES["you"])
    partner = _partner_name(user)
    return {
        "messages": [
            {"type": "bot", "text": "Here\u2019s more about your match:"},
            {
                "type": "match_card",
                "score": match["score"], "of": match["of"],
                "alignment": match["alignment"], "flags": match["flags"],
                "actions": [
                    {"label": "Connect", "action": "connect"},
                    {"label": "Pass", "action": "pass"},
                ],
                "revealed": True, "partner_name": partner,
            },
        ],
        "ui_patch": {"header_title": "RoomieAgent", "header_subtitle": f"Match: {partner}", "mode": "private"},
    }


def _h_confirmed(user):
    partner = _partner_name(user)
    return {
        "messages": [
            {"type": "bot", "text": f"You and {partner} are now connected! \U0001F389 Setting up your house group chat..."},
            {"type": "system", "text": f"Connected with {partner}"},
        ],
        "ui_patch": {"header_title": "RoomieAgent", "header_subtitle": f"Connected with {partner}", "mode": "private"},
    }




# ===================================================================
# FRIENDS FLOW (event planning, ~6 steps)
# ===================================================================

def _friends_step(user):
    st = _get(user)
    step = st["chats"]["friends"]["step"]

    if step == 0:   return _f_intro(user)
    elif step == 1: return _f_events(user)
    elif step == 2: return _f_picked(user)
    elif step == 3: return _f_carpool(user)
    elif step == 4: return _f_confirmed(user)
    else:
        return {"messages": [{"type": "bot", "text": "Plan complete! \U0001F389"}], "ui_patch": {}}


def _advance_friends(user, action, value):
    st = _get(user)
    fs = st["chats"]["friends"]
    fs["step"] = fs["step"] + 1
    return _friends_step(user)


def _f_intro(user):
    msgs = [
        {"type": "system", "text": "ASU Friends \U0001F389"},
        {"type": "bot", "text": "Yo this week was brutal. Anyone down for something fun this weekend? \U0001F629", "sender": "tejas"},
        {"type": "bot", "text": "YES. I need to get out of the library", "sender": "shreeya"},
        {"type": "bot", "text": "I\u2019m in if it\u2019s not too late \u2014 got a morning lab Monday", "sender": "rishi"},
        {
            "type": "notice_card",
            "title": "\U0001F389 Plan something?",
            "body": "Your friends are looking for weekend plans. Want to join?",
            "cta": "I\u2019m down! What\u2019s happening?",
            "action": "next",
        },
    ]
    return {
        "messages": msgs,
        "ui_patch": {"header_title": "ASU Friends \U0001F389", "header_subtitle": "You, Tejas, Shreeya, Rishi", "mode": "friends"},
    }


def _f_events(user):
    return {
        "messages": [
            {"type": "bot", "text": "Found some events this weekend:"},
            {
                "type": "notice_card",
                "title": "\U0001F3AA This Weekend at ASU",
                "body": "\U0001F3B5 Fri \u2014 Lantern Fest @ Tempe Town Lake, 7 pm\n\U0001F3C0 Sat \u2014 ASU vs UCLA Watch Party @ MU, 5 pm\n\U0001F3A8 Sat \u2014 Art Walk @ Roosevelt Row, 6\u20139 pm",
                "cta": "Watch Party sounds fun!",
                "action": "pick_event",
            },
        ],
        "ui_patch": {"header_title": "ASU Friends \U0001F389", "header_subtitle": "You, Tejas, Shreeya, Rishi", "mode": "friends"},
    }


def _f_picked(user):
    return {
        "messages": [
            {"type": "bot", "text": "LET\u2019S GO \U0001F3C0 I\u2019m 100% in", "sender": "tejas"},
            {"type": "bot", "text": "Down! I can bring snacks", "sender": "shreeya"},
            {"type": "bot", "text": "In! It ends by 8 right? That works", "sender": "rishi"},
            {"type": "bot", "text": "Everyone\u2019s in! Let me figure out rides\u2026"},
            {
                "type": "notice_card",
                "title": "\U0001F697 Plan carpool?",
                "body": "4 people going \u2014 let me group by campus for rides.",
                "cta": "Plan the carpool",
                "action": "carpool",
            },
        ],
        "ui_patch": {"header_title": "ASU Friends \U0001F389", "header_subtitle": "Watch Party \u2014 4 going", "mode": "friends"},
    }


def _f_carpool(user):
    return {
        "messages": [
            {"type": "bot", "text": "Carpool plan ready:"},
            {
                "type": "notice_card",
                "title": "\U0001F697 Carpool Groups",
                "body": "Tempe: You, Shreeya, Rishi \u2192 walk / light rail\nDowntown: Tejas \u2192 drives, 2 spare seats\n\nMeet at MU 202 by 4:30 pm",
                "cta": "Confirm plan",
                "action": "confirm",
            },
            {"type": "bot", "text": "I can grab anyone near Downtown campus on the way!", "sender": "tejas"},
            {"type": "bot", "text": "Rishi and I can walk from Hayden. See you all there!", "sender": "shreeya"},
        ],
        "ui_patch": {"header_title": "ASU Friends \U0001F389", "header_subtitle": "Carpool sorted", "mode": "friends"},
    }


def _f_confirmed(user):
    return {
        "messages": [
            {"type": "signed", "text": "Saturday plan confirmed \u2014 ASU vs UCLA Watch Party!"},
            {"type": "bot", "text": "Let\u2019s gooo \U0001F531", "sender": "rishi"},
            {"type": "bot", "text": "FORKS UP \U0001F531\U0001F531\U0001F531", "sender": "tejas"},
        ],
        "ui_patch": {"header_title": "ASU Friends \U0001F389", "header_subtitle": "Saturday \u2014 confirmed!", "mode": "friends"},
    }


# ===================================================================
# HOUSE FLOW (chore splitting, ~4 steps)
# ===================================================================

def _house_step(user):
    st = _get(user)
    step = st["chats"]["house"]["step"]

    if step == 0:   return _o_intro(user)
    elif step == 1: return _o_chores(user)
    elif step == 2: return _o_result(user)
    elif step == 3: return _o_done(user)
    else:
        return {"messages": [{"type": "bot", "text": "House all set! \U0001F3E1"}], "ui_patch": {}}


def _advance_house(user, action, value):
    st = _get(user)
    hs = st["chats"]["house"]
    hs["step"] = hs["step"] + 1
    return _house_step(user)


def _o_intro(user):
    return {
        "messages": [
            {"type": "system", "text": "Our Place \U0001F3E1"},
            {"type": "bot", "text": "OK the apartment is a mess. We need a chore system \U0001F605", "sender": "arjun"},
            {"type": "bot", "text": "Agreed. Last week nobody took out the trash until it overflowed", "sender": "shreeya"},
            {"type": "bot", "text": "My bad\u2026 thought it was Arjun\u2019s turn", "sender": "tejas"},
            {"type": "bot", "text": "I can help split chores fairly! Everyone picks preferences and I\u2019ll assign what works best."},
            {
                "type": "notice_card",
                "title": "\U0001F9F9 Split chores?",
                "body": "Tap below to start. Everyone picks what they like and I\u2019ll figure out the fairest split.",
                "cta": "Let\u2019s do it",
                "action": "start_chores",
            },
        ],
        "ui_patch": {"header_title": "Our Place \U0001F3E1", "header_subtitle": "You, Arjun, Shreeya, Tejas", "mode": "house"},
    }


def _o_chores(user):
    """Delegate to existing chore solver via web.py."""
    return {
        "messages": "__chores__",
        "ui_patch": {"header_title": "Our Place \U0001F3E1", "header_subtitle": "Splitting chores\u2026", "mode": "house"},
        "post_messages": [],
    }


def _o_result(user):
    return {
        "messages": [
            {"type": "bot", "text": "That\u2019s actually fair. I\u2019ll take the trash since I\u2019m closest to the dumpster", "sender": "arjun"},
            {"type": "bot", "text": "Works for me! Saturday bathroom deep clean is fine", "sender": "shreeya"},
            {"type": "bot", "text": "I can cook Fridays \U0001F373 taco night every week?", "sender": "tejas"},
            {
                "type": "notice_card",
                "title": "\u2705 Approve chore plan?",
                "body": "Everyone seems happy with the split. Lock it in?",
                "cta": "Approve",
                "action": "approve_chores",
            },
        ],
        "ui_patch": {"header_title": "Our Place \U0001F3E1", "header_subtitle": "Review assignments", "mode": "house"},
    }


def _o_done(user):
    return {
        "messages": [
            {"type": "signed", "text": "Chore schedule locked in!"},
            {"type": "bot", "text": "This house is going to be SO much better this semester", "sender": "tejas"},
            {"type": "bot", "text": "Weekend hangout to celebrate? \U0001F389", "sender": "shreeya"},
        ],
        "ui_patch": {"header_title": "Our Place \U0001F3E1", "header_subtitle": "All set!", "mode": "house"},
    }


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------

def reset(user=None):
    if user:
        _state.pop(user, None)
    else:
        _state.clear()
