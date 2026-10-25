#!/usr/bin/env python3
"""ASU campus search — classes, events, news, people.

All endpoints are public. No API keys needed. Pure stdlib.

Usage:
    python3 scripts/asu_search.py classes --subject CSE --number 240
    python3 scripts/asu_search.py classes --keywords "artificial intelligence"
    python3 scripts/asu_search.py classes --subject CSE --number 240 --open-only
    python3 scripts/asu_search.py events --keywords "career fair"
    python3 scripts/asu_search.py events
    python3 scripts/asu_search.py news --keywords "research"
    python3 scripts/asu_search.py news
    python3 scripts/asu_search.py people --query "machine learning"
    python3 scripts/asu_search.py terms

Exit codes:
    0  success
    1  error (network, bad input, no results for required field)
"""

import argparse
import json
import re
import sys
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from html.parser import HTMLParser


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

def fetch_json(url, params=None, headers=None):
    if params:
        url = f"{url}?{urlencode(params)}"
    req = Request(url, headers=headers or {})
    req.add_header("User-Agent", "CubbieSkill/1.0")
    with urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def fetch_html(url, params=None):
    if params:
        url = f"{url}?{urlencode(params)}"
    req = Request(url)
    req.add_header("User-Agent", "CubbieSkill/1.0")
    req.add_header("Accept", "text/html")
    with urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _clean_html(text):
    """Strip HTML tags and &nbsp; from API responses."""
    if not text:
        return ""
    return re.sub(r"<[^>]+>|&nbsp;", "", text).strip()


# ---------------------------------------------------------------------------
# Classes
# ---------------------------------------------------------------------------

CLASS_API = "https://eadvs-cscc-catalog-api.apps.asu.edu/catalog-microservices/api/v1/search"
CLASS_HEADERS = {
    "Authorization": "Bearer null",
    "Origin": "https://catalog.apps.asu.edu",
    "Referer": "https://catalog.apps.asu.edu/",
}


def get_current_term():
    data = fetch_json(f"{CLASS_API}/terms", headers=CLASS_HEADERS)
    current = data.get("currentTerm", [])
    if current:
        return str(current[0]["value"])
    full = data.get("fullList", [])
    return str(full[0]["value"]) if full else ""


def search_classes(term_code, subject=None, catalog_number=None, keywords=None,
                   instructor=None, open_only=False, max_results=25):
    params = {
        "refine": "Y", "term": term_code, "searchType": "all",
        "campusOrOnlineSelection": "A", "honors": "F", "promod": "F",
    }
    if subject:
        params["subject"] = subject.upper()
    if catalog_number:
        params["catalogNbr"] = catalog_number
    if keywords:
        params["keywords"] = keywords
    if instructor:
        params["instructorName"] = instructor

    data = fetch_json(f"{CLASS_API}/classes", params, CLASS_HEADERS)
    classes = data.get("classes", [])
    total = int((data.get("total") or {}).get("value", len(classes)))

    results = []
    for entry in classes[:max_results]:
        c = entry.get("CLAS", entry)
        seat = entry.get("seatInfo", {})

        seats_total = int(seat.get("ENRL_CAP", 0) or c.get("ENRLCAP", 0) or 0)
        seats_taken = int(seat.get("ENRL_TOT", 0) or c.get("ENRLTOT", 0) or 0)
        seats_open = seats_total - seats_taken

        if open_only and seats_open <= 0:
            continue

        day_map = [("MON", "M"), ("TUES", "Tu"), ("WED", "W"),
                   ("THURS", "Th"), ("FRI", "F"), ("SAT", "Sa"), ("SUN", "Su")]
        days = "".join(abbr for key, abbr in day_map if c.get(key) == "Y")

        start = _clean_html(c.get("STARTTIME"))
        end = _clean_html(c.get("ENDTIME"))
        location = c.get("DESCR3") or c.get("LOCATION") or ""
        loc_buildings = entry.get("LOCATIONBUILDING") or []
        building = loc_buildings[0].get("NAME", "") if loc_buildings else c.get("DESCR1") or ""

        instructors = []
        for inst in (entry.get("instructors") or []):
            if isinstance(inst, dict):
                name = inst.get("INSTR_NAME") or inst.get("name") or ""
                if name:
                    instructors.append(name)

        results.append({
            "course": f"{c.get('SUBJECT', '')} {c.get('CATALOGNBR', '')}".strip(),
            "title": c.get("COURSETITLELONG") or c.get("TITLE") or "",
            "section": c.get("CLASSSECTION", ""),
            "class_number": c.get("CLASSNBR", ""),
            "days": days or "Online/Async",
            "time": f"{start}-{end}" if start else "Async",
            "location": f"{location} - {building}".strip(" -") if building else location,
            "campus": c.get("CAMPUS", ""),
            "instructors": instructors,
            "seats_total": seats_total,
            "seats_taken": seats_taken,
            "seats_open": seats_open,
            "units": c.get("UNITSMINIMUM", ""),
            "enrollment_status": "Open" if c.get("ENRLSTAT") == "O" else "Closed",
        })

    return {"total_found": total, "showing": len(results), "classes": results}


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

class EventParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.events = []
        self._in_card = self._in_title = self._in_date = False
        self._in_time = self._in_location = False
        self._current = {}
        self._text = ""

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = a.get("class", "")
        if tag == "li" and "card-event" in cls:
            self._in_card = True
            self._current = {}
        if self._in_card:
            if tag == "h3" and "card-title" in cls:
                self._in_title = True
            if tag == "a" and self._in_title:
                href = a.get("href", "")
                if "/event/" in href:
                    self._current["url"] = f"https://asuevents.asu.edu{href}"
            if "field-event-date" in cls:
                self._in_date = True; self._text = ""
            if "field-event-date-end" in cls:
                self._in_time = True; self._text = ""
            if "field-asu-events-location" in cls:
                self._in_location = True; self._text = ""

    def handle_data(self, data):
        if self._in_title:
            self._current.setdefault("title", "")
            self._current["title"] += data.strip()
        if self._in_date or self._in_time or self._in_location:
            self._text += data.strip() + " "

    def handle_endtag(self, tag):
        if tag == "h3" and self._in_title:
            self._in_title = False
        if tag == "div":
            if self._in_date:
                self._current["date"] = self._text.strip(); self._in_date = False
            if self._in_time:
                self._current["time"] = self._text.strip(); self._in_time = False
            if self._in_location:
                self._current["location"] = self._text.strip(); self._in_location = False
        if tag == "li" and self._in_card:
            self._in_card = False
            if self._current.get("title"):
                self.events.append(self._current)


def search_events(keywords=None, limit=10):
    events = []
    for page in range(3):
        html = fetch_html("https://asuevents.asu.edu/", {"page": page})
        parser = EventParser()
        parser.feed(html)
        events.extend(parser.events)
        if not parser.events:
            break
    if keywords:
        kw = keywords.lower()
        events = [e for e in events if kw in
                  f"{e.get('title', '')} {e.get('location', '')}".lower()]
    return {"events": events[:limit]}


# ---------------------------------------------------------------------------
# News
# ---------------------------------------------------------------------------

class NewsParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stories = []
        self._in_td = self._in_link = False
        self._current = {}
        self._td_text = ""

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "td":
            self._in_td = True; self._current = {}; self._td_text = ""
        if tag == "a" and self._in_td:
            href = a.get("href", "")
            if href and len(href) > 10 and href[0] == "/" and href[1:3].isdigit():
                self._current["url"] = f"https://news.asu.edu{href}"
                self._in_link = True

    def handle_data(self, data):
        if self._in_link:
            self._current.setdefault("title", "")
            self._current["title"] += data.strip()
        if self._in_td:
            self._td_text += data.strip() + " "

    def handle_endtag(self, tag):
        if tag == "a" and self._in_link:
            self._in_link = False
        if tag == "td" and self._in_td:
            self._in_td = False
            if self._current.get("title"):
                self._current["summary"] = self._td_text.strip()
                self.stories.append(self._current)


def search_news(keywords=None, limit=8):
    if keywords:
        html = fetch_html("https://news.asu.edu/search", {"search": keywords})
    else:
        html = fetch_html("https://news.asu.edu/")
    parser = NewsParser()
    parser.feed(html)
    return {"stories": parser.stories[:limit]}


# ---------------------------------------------------------------------------
# People
# ---------------------------------------------------------------------------

PEOPLE_API = "https://search.asu.edu/api/v1"


def search_people(query, limit=5):
    data = fetch_json(
        f"{PEOPLE_API}/webdir-profiles/faculty-staff",
        {"query": query, "page": 1, "size": limit * 3, "client": "asuis", "sort-by": ""},
    )
    results = []
    seen = set()
    for item in data.get("results", []):
        def raw(key, _item=item):
            val = _item.get(key)
            return val.get("raw") if isinstance(val, dict) else val

        asurite = raw("asurite_id")
        name = raw("display_name")
        if not asurite or not name or asurite in seen:
            continue
        seen.add(asurite)

        def first_list(key, _item=item):
            val = raw(key, _item)
            return val[0] if isinstance(val, list) and val else val

        eid = raw("eid")
        results.append({
            "name": name,
            "title": first_list("primary_title") or first_list("working_title") or "",
            "department": first_list("departments") or "",
            "email": raw("email_address") or "",
            "phone": first_list("phone") or "",
            "campus": first_list("campus") or "",
            "profile": f"https://search.asu.edu/profile/{eid}" if eid else "",
        })
    return {"people": results[:limit]}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="ASU campus search")
    sub = parser.add_subparsers(dest="command", required=True)

    p_class = sub.add_parser("classes")
    p_class.add_argument("--subject")
    p_class.add_argument("--number")
    p_class.add_argument("--keywords")
    p_class.add_argument("--instructor")
    p_class.add_argument("--term")
    p_class.add_argument("--open-only", action="store_true")
    p_class.add_argument("--max", type=int, default=25)

    p_event = sub.add_parser("events")
    p_event.add_argument("--keywords")
    p_event.add_argument("--limit", type=int, default=10)

    p_news = sub.add_parser("news")
    p_news.add_argument("--keywords")
    p_news.add_argument("--limit", type=int, default=8)

    p_people = sub.add_parser("people")
    p_people.add_argument("--query", required=True)
    p_people.add_argument("--limit", type=int, default=5)

    sub.add_parser("terms")

    args = parser.parse_args([a for a in sys.argv[1:] if a != "--sample"])
    use_sample = "--sample" in sys.argv

    if use_sample:
        # Return minimal sample data for offline testing
        samples = {
            "classes": {"total_found": 1, "showing": 1, "term": "2271", "classes": [
                {"course": "CSE 310", "title": "Data Structures and Algorithms",
                 "section": "1001", "class_number": "11198", "days": "MW",
                 "time": "9:00 AM-10:15 AM", "location": "Tempe - COOR170",
                 "campus": "TEMPE", "instructors": [], "seats_total": 150,
                 "seats_taken": 71, "seats_open": 79, "units": "3",
                 "enrollment_status": "Open"}]},
            "events": {"events": [{"title": "Fall Career Fair", "date": "Nov 1",
                        "time": "10am-3pm", "location": "Tempe campus",
                        "url": "https://asuevents.asu.edu/event/sample"}]},
            "news": {"stories": [{"title": "ASU Research Breakthrough", "date": "2026-10-24",
                      "summary": "Sample story", "url": "https://news.asu.edu/sample"}]},
            "people": {"people": [{"name": "Sample Professor", "title": "Professor",
                        "department": "School of Computing", "email": "sample@asu.edu",
                        "phone": "", "campus": "Tempe",
                        "profile": "https://search.asu.edu/profile/0"}]},
            "terms": {"current_term": "2271", "recent_terms": [
                       {"code": "2271", "label": "Spring 2027"}]},
        }
        print(json.dumps(samples.get(args.command, {"error": "unknown command"}), indent=2))
        return

    try:
        if args.command == "terms":
            term = get_current_term()
            data = fetch_json(f"{CLASS_API}/terms", headers=CLASS_HEADERS)
            terms = data.get("fullList", [])[:10]
            result = {
                "current_term": term,
                "recent_terms": [{"code": str(t["value"]), "label": t.get("label", "")}
                                 for t in terms],
            }
        elif args.command == "classes":
            term = args.term or get_current_term()
            result = search_classes(
                term, subject=args.subject, catalog_number=args.number,
                keywords=args.keywords, instructor=args.instructor,
                open_only=args.open_only, max_results=args.max,
            )
            result["term"] = term
        elif args.command == "events":
            result = search_events(keywords=args.keywords, limit=args.limit)
        elif args.command == "news":
            result = search_news(keywords=args.keywords, limit=args.limit)
        elif args.command == "people":
            result = search_people(query=args.query, limit=args.limit)
        else:
            parser.print_help()
            sys.exit(1)

        print(json.dumps(result, indent=2))
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
