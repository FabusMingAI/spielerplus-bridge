from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from spielerplus_mcp.feeds import validate_url, parse_events


@pytest.mark.parametrize("value", [
    "http://www.spielerplus.de/events/ics?t=ABC&u=XYZ",
    "https://evil.example/events/ics?t=ABC&u=XYZ",
    "https://www.spielerplus.de.evil.example/events/ics?t=ABC&u=XYZ",
    "https://www.spielerplus.de/other/path?t=ABC&u=XYZ",
    "file:///etc/passwd",
])
def test_reject_untrusted_urls(value):
    with pytest.raises(ValueError):
        validate_url(value)


def test_webcal_is_https():
    assert validate_url(
        "webcal://www.spielerplus.de/events/ics?t=EXAMPLE&u=EXAMPLE"
    ) == "https://www.spielerplus.de/events/ics?t=EXAMPLE&u=EXAMPLE"


ICS = b"""BEGIN:VCALENDAR\r
VERSION:2.0\r
PRODID:-//Testing//EN\r
BEGIN:VEVENT\r
UID:demo@example.invalid\r
DTSTAMP:20260101T000000Z\r
DTSTART:20261201T180000Z\r
DTEND:20261201T193000Z\r
SUMMARY:Training\r
LOCATION:Sportplatz\r
END:VEVENT\r
END:VCALENDAR\r
"""


def test_parses_event_and_timezone():
    tz = ZoneInfo("Europe/Berlin")
    events = parse_events(
        ICS,
        datetime(2026, 12, 1, tzinfo=tz),
        datetime(2026, 12, 2, tzinfo=tz),
        "Team A",
        tz,
    )
    assert len(events) == 1
    assert events[0]["team"] == "Team A"
    assert events[0]["title"] == "Training"
    assert events[0]["start"].startswith("2026-12-01T19:00:00")
    assert events[0]["location"] == "Sportplatz"
