"""One bounded calendar fetch shared by all subscription entities."""

from datetime import timedelta
import asyncio
import logging

import aiohttp
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import CONF_URL, DOMAIN
from .events import MAX_ICS_BYTES, calendar_notice, detect_changes, parse_calendar
from .attendance import AccountError
from .account import SpielerPlusAccount

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
        self.calendar_notice = None
        self.account_client = None
        self.participation = {}
        self.account_error = None
        self.account_last_success = None
        options = entry.options
        if all(
            options.get(key)
            for key in ("account_email", "account_password", "membership_id")
        ):
            self.account_client = SpielerPlusAccount(
                options["account_email"],
                options["account_password"],
                options["membership_id"],
            )

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
        self.calendar_notice = calendar_notice(events)
        if self.calendar_notice:
            events = []
        # Optional account failures must not invalidate a successful ICS fetch.
        if self.account_client is not None:
            try:
                self.participation = await asyncio.wait_for(
                    self.account_client.async_fetch(), timeout=45
                )
                self.account_last_success = dt_util.utcnow()
                self.account_error = None
            except AccountError as exc:
                self.account_error = exc.code
            except TimeoutError:
                self.account_error = "cannot_connect"
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
