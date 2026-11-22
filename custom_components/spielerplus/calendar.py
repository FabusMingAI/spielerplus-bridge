"""Read-only calendar using the shared subscription coordinator."""

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.const import CONF_NAME
from homeassistant.util import dt as dt_util
from .const import DOMAIN
from .events import upcoming
from .entity import SpielerPlusEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([SpielerPlusCalendar(hass.data[DOMAIN][entry.entry_id], entry)])


def calendar_event(event):
    return CalendarEvent(
        start=event.start.date() if event.all_day else event.start,
        end=event.end.date() if event.all_day else event.end,
        summary=event.title,
        description=event.description,
        location=event.location,
        uid=event.uid,
    )


class SpielerPlusCalendar(SpielerPlusEntity, CalendarEntity):
    _attr_icon = "mdi:calendar-account"
    _attr_has_entity_name = False

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_name = f"SpielerPlus {entry.data[CONF_NAME]}"
        # Preserve the existing calendar entity and its automations.
        self._attr_unique_id = entry.entry_id

    @property
    def event(self):
        events = upcoming(self.coordinator.data or [], dt_util.utcnow())
        return calendar_event(events[0]) if events else None

    async def async_get_events(self, hass, start_date, end_date):
        return [
            calendar_event(event)
            for event in (self.coordinator.data or [])
            if not event.cancelled
            and event.end > dt_util.as_utc(start_date)
            and event.start < dt_util.as_utc(end_date)
        ]
