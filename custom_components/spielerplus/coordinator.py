"""One bounded calendar fetch shared by all subscription entities."""

from datetime import timedelta
import logging

import aiohttp
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import CONF_URL, DOMAIN
from .events import MAX_ICS_BYTES, detect_changes, parse_calendar

_LOGGER = logging.getLogger(__name__)


class SpielerPlusCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry):
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(minutes=15),
        )
        self.entry = entry
        self.last_success = None
        self.last_change = None
        self.changes = []
        self.last_error = None
        self.window_end = None

    async def _async_update_data(self):
        now = dt_util.utcnow()
        try:
            session = async_get_clientsession(self.hass)
            async with session.get(
                self.entry.data[CONF_URL],
                timeout=aiohttp.ClientTimeout(total=20),
                allow_redirects=False,
            ) as response:
                if response.status != 200:
                    raise ValueError(f"HTTP {response.status}")
                chunks, total = [], 0
                async for chunk in response.content.iter_chunked(64 * 1024):
                    total += len(chunk)
                    if total > MAX_ICS_BYTES:
                        raise ValueError("Calendar feed too large")
                    chunks.append(chunk)
            events = await self.hass.async_add_executor_job(
                parse_calendar,
                b"".join(chunks),
                now - timedelta(days=1),
                now + timedelta(days=366),
                dt_util.DEFAULT_TIME_ZONE,
            )
        except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
            self.last_error = type(exc).__name__
            raise UpdateFailed(f"Calendar refresh failed ({self.last_error})") from None
        self.last_success = now
        self.last_error = None
        if self.data is not None:
            changes = detect_changes(self.data, events, now, self.window_end)
            if changes:
                self.last_change = now
                self.changes = changes[-10:]
                for change in changes:
                    self.hass.bus.async_fire(
                        f"{DOMAIN}_calendar_changed",
                        {
                            "entry_id": self.entry.entry_id,
                            **change,
                        },
                    )
        self.window_end = now + timedelta(days=366)
        return events
