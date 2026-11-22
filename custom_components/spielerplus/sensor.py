"""Next events, countdown and diagnostics."""

import math
from datetime import timedelta
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.util import dt as dt_util
from .const import DOMAIN
from .events import upcoming
from .attendance import STATUSES, event_ref
from .entity import SpielerPlusEntity

SENSORS = (
    ("next_training", "mdi:run", SensorDeviceClass.TIMESTAMP),
    ("next_game", "mdi:soccer", SensorDeviceClass.TIMESTAMP),
    ("countdown", "mdi:timer-outline", SensorDeviceClass.DURATION),
    ("events_week", "mdi:calendar-week", None),
    ("last_success", "mdi:cloud-check-outline", SensorDeviceClass.TIMESTAMP),
    ("last_change", "mdi:calendar-sync", SensorDeviceClass.TIMESTAMP),
)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        SpielerPlusSensor(coordinator, entry, *description) for description in SENSORS
    ]
    if coordinator.account_client is not None:
        entities.extend(
            [
                SpielerPlusParticipation(coordinator, entry, kind)
                for kind in ("training", "game")
            ]
        )
        entities.append(SpielerPlusAccountFetch(coordinator, entry))
    async_add_entities(entities)


class SpielerPlusSensor(SpielerPlusEntity, SensorEntity):
    def __init__(self, coordinator, entry, key, icon, device_class):
        super().__init__(coordinator, entry)
        self.key = key
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_icon = icon
        self._attr_device_class = device_class
        if key in {"last_success", "last_change"}:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        if key == "countdown":
            self._attr_native_unit_of_measurement = UnitOfTime.MINUTES

    @property
    def available(self):
        return self.key in {"last_success", "last_change"} or super().available

    def _next(self):
        kind = {"next_training": "training", "next_game": "game"}.get(self.key)
        events = upcoming(self.coordinator.data or [], dt_util.utcnow(), kind)
        return events[0] if events else None

    @property
    def native_value(self):
        if self.key == "last_success":
            return self.coordinator.last_success
        if self.key == "last_change":
            return self.coordinator.last_change
        if self.key == "events_week":
            now = dt_util.utcnow()
            return sum(
                event.start < now + timedelta(days=7)
                for event in upcoming(self.coordinator.data or [], now)
            )
        event = self._next()
        if event is None:
            return None
        if self.key == "countdown":
            return max(
                0, math.ceil((event.start - dt_util.utcnow()).total_seconds() / 60)
            )
        return event.start

    @property
    def extra_state_attributes(self):
        if self.key == "last_success":
            return {
                "last_error": self.coordinator.last_error,
                "poll_interval_minutes": 15,
                "cached_events": len(self.coordinator.data or []),
            }
        if self.key == "last_change":
            return {
                "changes": self.coordinator.changes,
                "baseline": "since last integration start",
            }
        if self.key == "events_week":
            now = dt_util.utcnow()
            return {
                "events": [
                    event.details()
                    for event in upcoming(self.coordinator.data or [], now)
                    if event.start < now + timedelta(days=7)
                ]
            }
        event = self._next()
        return event.details() if event else {}


class SpielerPlusParticipation(SpielerPlusEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(STATUSES)
    _attr_icon = "mdi:account-check-outline"

    def __init__(self, coordinator, entry, kind):
        super().__init__(coordinator, entry)
        self.kind = kind
        self._attr_unique_id = f"{entry.entry_id}_{kind}_participation"
        self._attr_translation_key = f"{kind}_participation"

    def _summary(self):
        events = upcoming(self.coordinator.data or [], dt_util.utcnow(), self.kind)
        if not events:
            return None
        key = event_ref(events[0].url)
        return self.coordinator.participation.get(key) if key else None

    @property
    def available(self):
        return (
            super().available
            and self.coordinator.account_error is None
            and self.coordinator.account_last_success is not None
            and self._summary() is not None
        )

    @property
    def native_value(self):
        summary = self._summary()
        return summary["own_status"] if summary else None

    @property
    def extra_state_attributes(self):
        summary = self._summary()
        return (
            {
                "counts": summary["counts"],
                **summary["times"],
                "detail_error": summary["detail_error"],
                "coverage": "first_5_listed_events",
            }
            if summary
            else {}
        )


class SpielerPlusAccountFetch(SpielerPlusEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "account_last_success"
    _attr_icon = "mdi:account-clock-outline"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_account_last_success"

    @property
    def available(self):
        return True

    @property
    def native_value(self):
        return self.coordinator.account_last_success

    @property
    def extra_state_attributes(self):
        return {
            "last_error": self.coordinator.account_error,
            "events_loaded": len(self.coordinator.participation),
            "coverage": "first_5_listed_events",
            "member_names_stored": False,
        }
