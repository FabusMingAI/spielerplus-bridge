"""Parsing and validation of private SpielerPlus ICS feeds."""
from datetime import date, datetime, time, timedelta
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from icalendar import Calendar
import recurring_ical_events

MAX_ICS_BYTES = 5_000_000


def validate_url(url: str) -> str:
    value = url.strip()
    if value.startswith("webcal://"):
        value = "https://" + value[len("webcal://"):]
    parsed = urlparse(value)
    if (parsed.scheme != "https" or parsed.netloc != "www.spielerplus.de"
            or parsed.path != "/events/ics" or not parsed.query
            or parsed.username or parsed.password or parsed.fragment):
        raise ValueError("Only official SpielerPlus HTTPS ICS URLs are accepted")
    return value


def as_datetime(value, timezone: ZoneInfo):
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone) if value.tzinfo is None else value.astimezone(timezone)
    return datetime.combine(value, time.min, tzinfo=timezone)


def parse_events(raw: bytes, start: datetime, end: datetime, team: str, timezone: ZoneInfo):
    if len(raw) > MAX_ICS_BYTES:
        raise ValueError("Calendar feed too large")
    calendar = Calendar.from_ical(raw)
    records = []
    for item in recurring_ical_events.of(calendar).between(start, end):
        begins = item.get("DTSTART")
        if not begins:
            continue
        ends = item.get("DTEND")
        start_value = begins.dt
        end_value = ends.dt if ends else start_value + (
            timedelta(days=1) if isinstance(start_value, date) and not isinstance(start_value, datetime)
            else timedelta(hours=1)
        )
        begin = as_datetime(start_value, timezone)
        finish = as_datetime(end_value, timezone)
        if finish <= start or begin >= end:
            continue
        records.append({
            "team": team,
            "title": str(item.get("SUMMARY", "Termin")),
            "start": begin.isoformat(),
            "end": finish.isoformat(),
            "all_day": isinstance(start_value, date) and not isinstance(start_value, datetime),
            "location": str(item.get("LOCATION", "")),
            "description": str(item.get("DESCRIPTION", "")),
            "uid": str(item.get("UID", "")),
        })
    return sorted(records, key=lambda item: item["start"])
