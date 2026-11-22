"""Calendar semantics without importing Home Assistant's lifecycle."""

from dataclasses import replace
from datetime import datetime, timedelta
import importlib.util
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

import pytest

spec = importlib.util.spec_from_file_location(
    "spielerplus_event_records",
    Path(__file__).parents[1] / "custom_components/spielerplus/events.py",
)
events = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = events
spec.loader.exec_module(events)
TZ = ZoneInfo("Europe/Berlin")
NOW = datetime(2026, 11, 22, 12, tzinfo=TZ)
START = datetime(2026, 11, 25, 17, 45, tzinfo=TZ)


def record(**changes):
    event = events.Event(
        "stable:", "stable", "Training", START, START + timedelta(hours=1), False
    )
    return replace(event, **changes)


def ics(*lines):
    return (
        "\r\n".join(
            [
                "BEGIN:VCALENDAR",
                "VERSION:2.0",
                "PRODID:-//Tests//EN",
                "BEGIN:VEVENT",
                "UID:stable",
                "DTSTART:20261125T164500Z",
                "DTEND:20261125T174500Z",
                "SUMMARY:Training",
                *lines,
                "END:VEVENT",
                "END:VCALENDAR",
                "",
            ]
        )
    ).encode()


@pytest.mark.parametrize(
    "title,kind",
    [
        ("Training", "training"),
        ("Torwarttraining", "other"),
        ("Trainingslager", "training"),
        ("Spiel: FC Demo - SV Beispiel", "game"),
        ("Freundschaftsspiel", "game"),
        ("Match day", "game"),
        ("Elternabend", "other"),
        ("Besprechung Spielplanung", "other"),
    ],
)
def test_explicit_classification(title, kind):
    assert events.classify(title) == kind


def test_metadata_and_timezone():
    result = events.parse_calendar(
        ics(
            "GEO:48.1;11.5",
            "LOCATION:Demo arena",
            "STATUS:TENTATIVE",
            "URL:https://www.spielerplus.de/events/view?id=123",
        ),
        NOW,
        NOW + timedelta(days=30),
        TZ,
    )
    assert result[0].start == START
    assert result[0].latitude == 48.1
    assert result[0].longitude == 11.5
    assert result[0].status == "TENTATIVE"
    assert result[0].url.endswith("id=123")


@pytest.mark.parametrize(
    "url",
    [
        "https://www.spielerplus.de/events/ics?t=EXAMPLE&u=EXAMPLE",
        "https://www.spielerplus.de/events/ics/",
        "https://www.spielerplus.de/events/view?token=PRIVATE",
        "https://evil.example/event",
        "javascript:alert(1)",
    ],
)
def test_subscription_and_external_urls_never_exposed(url):
    assert events.event_url(url) == ""


def test_moved_event_is_one_update_not_delete_and_add():
    old = record()
    new = replace(old, start=START + timedelta(hours=2), end=START + timedelta(hours=3))
    change = events.detect_changes([old], [new], NOW)
    assert [item["change"] for item in change] == ["updated"]


def test_timestamp_only_change_is_ignored():
    first = events.parse_calendar(
        ics("DTSTAMP:20261101T120000Z"), NOW, NOW + timedelta(days=30), TZ
    )
    second = events.parse_calendar(
        ics("DTSTAMP:20261122T120000Z"), NOW, NOW + timedelta(days=30), TZ
    )
    assert events.detect_changes(first, second, NOW) == []


def test_added_removed_and_cancelled():
    event = record()
    assert events.detect_changes([], [event], NOW)[0]["change"] == "added"
    assert events.detect_changes([event], [], NOW)[0]["change"] == "removed"
    cancelled = replace(event, status="CANCELLED")
    assert events.detect_changes([event], [cancelled], NOW)[0]["change"] == "updated"
    assert events.upcoming([cancelled], NOW) == []


def test_expiry_and_rolling_horizon_are_not_changes():
    old = record(start=NOW - timedelta(days=2), end=NOW - timedelta(days=1))
    assert events.detect_changes([old], [], NOW) == []
    far = record(start=NOW + timedelta(days=366), end=NOW + timedelta(days=367))
    assert events.detect_changes([], [far], NOW, NOW + timedelta(days=365)) == []


def test_recurring_instances_have_distinct_keys_and_stable_identity():
    raw = ics("RRULE:FREQ=WEEKLY;COUNT=3")
    result = events.parse_calendar(raw, NOW, NOW + timedelta(days=30), TZ)
    assert len(result) == len({event.key for event in result}) == 3
    assert (
        events.detect_changes(result, result[1:], result[0].end + timedelta(seconds=1))
        == []
    )


def test_parsed_one_off_keeps_key_when_moved():
    raw = ics()
    shifted = raw.replace(b"164500Z", b"184500Z").replace(b"174500Z", b"194500Z")
    old = events.parse_calendar(raw, NOW, NOW + timedelta(days=30), TZ)
    new = events.parse_calendar(shifted, NOW, NOW + timedelta(days=30), TZ)
    assert old[0].key == new[0].key
    assert events.detect_changes(old, new, NOW)[0]["change"] == "updated"


def test_all_day_has_exclusive_end_and_dst_offset():
    raw = (
        ics()
        .replace(b"DTSTART:20261125T164500Z", b"DTSTART;VALUE=DATE:20261025")
        .replace(b"DTEND:20261125T174500Z", b"DTEND;VALUE=DATE:20261026")
    )
    start = datetime(2026, 10, 24, tzinfo=TZ)
    event = events.parse_calendar(raw, start, start + timedelta(days=4), TZ)[0]
    assert event.all_day
    assert event.start.utcoffset() == timedelta(hours=2)
    assert event.end.utcoffset() == timedelta(hours=1)


def test_empty_complete_calendar_is_valid():
    assert (
        events.parse_calendar(
            b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nEND:VCALENDAR\r\n",
            NOW,
            NOW + timedelta(days=30),
            TZ,
        )
        == []
    )


@pytest.mark.parametrize(
    "raw", [b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\n", b"x" * 5_000_001]
)
def test_invalid_and_oversize_calendar_rejected(raw):
    with pytest.raises(ValueError):
        events.parse_calendar(raw, NOW, NOW + timedelta(days=30), TZ)
