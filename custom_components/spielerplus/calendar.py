"""Read-only SpielerPlus calendar entities for Home Assistant."""
from datetime import date, datetime, time, timedelta
import logging

import aiohttp
from icalendar import Calendar
import recurring_ical_events
from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.const import CONF_NAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .const import CONF_URL

_LOGGER = logging.getLogger(__name__)
MAX_ICS_BYTES = 5_000_000


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([SpielerPlusCalendar(hass, entry)])


def parse_events(raw, start, end):
    calendar = Calendar.from_ical(raw)
    result = []
    for item in recurring_ical_events.of(calendar).between(start, end):
        begins = item.get("DTSTART")
        if not begins:
            continue
        ends = item.get("DTEND")
        start_at = begins.dt
        end_at = ends.dt if ends else start_at + (
            timedelta(days=1) if isinstance(start_at, date) and not isinstance(start_at, datetime)
            else timedelta(hours=1)
        )
        result.append(CalendarEvent(
            start=start_at,
            end=end_at,
            summary=str(item.get("SUMMARY", "Termin")),
            description=str(item.get("DESCRIPTION", "")),
            location=str(item.get("LOCATION", "")),
            uid=str(item.get("UID", "")),
        ))
    return sorted(result, key=lambda event: str(event.start))


def as_utc(value):
    if isinstance(value, date) and not isinstance(value, datetime):
        return dt_util.as_utc(datetime.combine(
            value, time.min, tzinfo=dt_util.DEFAULT_TIME_ZONE
        ))
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
    return dt_util.as_utc(value)


class SpielerPlusCalendar(CalendarEntity):
    _attr_icon = "mdi:calendar-account"
    _attr_should_poll = True

    def __init__(self, hass, entry):
        self._hass = hass
        self._url = entry.data[CONF_URL]
        self._attr_name = f"SpielerPlus {entry.data[CONF_NAME]}"
        self._attr_unique_id = entry.entry_id
        self._events = []
        self._last_fetch = None

    async def _fetch(self):
        now = dt_util.utcnow()
        if self._last_fetch and now - self._last_fetch < timedelta(minutes=15):
            return
        session = async_get_clientsession(self._hass)
        try:
            async with session.get(
                self._url,
                timeout=aiohttp.ClientTimeout(total=20),
                allow_redirects=False,
            ) as response:
                response.raise_for_status()
                raw = await response.content.read(MAX_ICS_BYTES + 1)
                if len(raw) > MAX_ICS_BYTES:
                    raise ValueError("ICS calendar feed exceeds 5 MB")
            self._events = parse_events(
                raw, now - timedelta(days=1), now + timedelta(days=366)
            )
            self._last_fetch = now
        except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
            _LOGGER.warning("Could not refresh SpielerPlus calendar (%s)", type(exc).__name__)

    @property
    def event(self):
        now = dt_util.utcnow()
        upcoming = [event for event in self._events if as_utc(event.end) > now]
        return min(upcoming, key=lambda event: as_utc(event.start)) if upcoming else None

    async def async_get_events(self, hass, start_date, end_date):
        await self._fetch()
        return [
            event for event in self._events
            if as_utc(event.end) > dt_util.as_utc(start_date)
            and as_utc(event.start) < dt_util.as_utc(end_date)
        ]

    async def async_update(self):
        await self._fetch()
