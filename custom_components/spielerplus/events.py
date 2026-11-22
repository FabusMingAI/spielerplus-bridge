"""Calendar records and change detection, independent of Home Assistant."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
import re
from urllib.parse import parse_qs, urlparse

from icalendar import Calendar
import recurring_ical_events

MAX_ICS_BYTES = 5_000_000


def classify(title):
    """Ambiguous titles remain 'other'."""
    if re.search(r"\b(training|trainings\w*|practice)\b", title, re.I):
        return "training"
    if re.search(
        r"\b(spiel|spieltag|match|game|turnier|tournament|freundschaftsspiel|testspiel|punktspiel)\b",
        title,
        re.I,
    ):
        return "game"
    return "other"


def event_url(value):
    """Expose official event pages, never the subscription URL."""
    parsed = urlparse(value)
    if (
        parsed.scheme != "https"
        or parsed.netloc != "www.spielerplus.de"
        or parsed.username
        or parsed.password
        or parsed.path.rstrip("/") == "/events/ics"
        or set(parse_qs(parsed.query)).intersection({"t", "u", "token", "key"})
    ):
        return ""
    return value


def as_datetime(value, timezone):
    if isinstance(value, datetime):
        return (
            value.replace(tzinfo=timezone)
            if value.tzinfo is None
            else value.astimezone(timezone)
        )
    return datetime.combine(value, time.min, tzinfo=timezone)


@dataclass(frozen=True)
class Event:
    key: str
    uid: str
    title: str
    start: datetime
    end: datetime
    all_day: bool
    location: str = ""
    description: str = ""
    status: str = "CONFIRMED"
    url: str = ""
    latitude: float | None = None
    longitude: float | None = None

    @property
    def kind(self):
        return classify(self.title)

    @property
    def cancelled(self):
        return self.status == "CANCELLED"

    def details(self):
        return {
            "title": self.title,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "all_day": self.all_day,
            "location": self.location,
            "description": self.description,
            "status": self.status,
            "event_type": self.kind,
            "event_url": self.url,
            "latitude": self.latitude,
            "longitude": self.longitude,
        }


def parse_calendar(raw, start, end, timezone):
    if len(raw) > MAX_ICS_BYTES:
        raise ValueError("Calendar feed too large")
    calendar = Calendar.from_ical(raw)
    if not raw.rstrip().upper().endswith(b"END:VCALENDAR"):
        raise ValueError("Incomplete calendar response")
    recurring_uids = {
        str(item.get("UID", ""))
        for item in calendar.walk("VEVENT")
        if item.get("RRULE")
    }
    records = []
    for item in recurring_ical_events.of(calendar).between(start, end):
        begins = item.get("DTSTART")
        if begins is None:
            continue
        value = begins.dt
        all_day = isinstance(value, date) and not isinstance(value, datetime)
        ends, duration = item.get("DTEND"), item.get("DURATION")
        finish = (
            ends.dt
            if ends is not None
            else value
            + (
                duration.dt
                if duration is not None
                else timedelta(days=1)
                if all_day
                else timedelta(hours=1)
            )
        )
        begin, finish = as_datetime(value, timezone), as_datetime(finish, timezone)
        if finish <= start or begin >= end:
            continue
        uid = str(item.get("UID", ""))
        occurrence = item.get("RECURRENCE-ID")
        suffix = (
            str(occurrence.dt)
            if uid in recurring_uids and occurrence is not None
            else ""
        )
        key = (
            f"{uid}:{suffix}"
            if uid
            else f"{begin.isoformat()}:{item.get('SUMMARY', '')}"
        )
        lat = lon = None
        geo = item.get("GEO")
        if geo is not None:
            try:
                lat, lon = float(geo.latitude), float(geo.longitude)
                if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                    lat = lon = None
            except (TypeError, ValueError, AttributeError):
                lat = lon = None
        records.append(
            Event(
                key=key,
                uid=uid,
                title=str(item.get("SUMMARY", "Termin")),
                start=begin,
                end=finish,
                all_day=all_day,
                location=str(item.get("LOCATION", "")),
                description=str(item.get("DESCRIPTION", "")),
                status=str(item.get("STATUS", "CONFIRMED")).upper(),
                url=event_url(str(item.get("URL", ""))),
                latitude=lat,
                longitude=lon,
            )
        )
    return sorted(records, key=lambda event: event.start)


def upcoming(events, now, kind=None):
    return sorted(
        (
            event
            for event in events
            if event.end > now
            and not event.cancelled
            and (kind is None or event.kind == kind)
        ),
        key=lambda event: event.start,
    )


def detect_changes(previous, current, now, until=None):
    """Do not report expiry of past events as deletion."""
    old, new = (
        {event.key: event for event in previous},
        {event.key: event for event in current},
    )
    result = []
    for key in sorted(old.keys() | new.keys()):
        before, after = old.get(key), new.get(key)
        if (
            before == after
            or max(event.end for event in (before, after) if event) <= now
        ):
            continue
        if before is None and until is not None and after.start >= until:
            continue
        kind = "added" if before is None else "removed" if after is None else "updated"
        result.append(
            {
                "change": kind,
                "uid": (after or before).uid,
                "before": before.details() if before else None,
                "after": after.details() if after else None,
            }
        )
    return result
