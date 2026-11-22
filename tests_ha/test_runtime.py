"""Run inside a Home Assistant container with the integration installed."""

from datetime import timedelta
import asyncio
import logging
import os
import sys

sys.path.insert(0, os.environ.get("HA_CONFIG", "/config"))
from tempfile import TemporaryDirectory
from types import MappingProxyType, SimpleNamespace
import unittest
from unittest.mock import patch, AsyncMock

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, HassJob, HassJobType
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util
from custom_components.spielerplus import coordinator as module
import custom_components.spielerplus as integration
from custom_components.spielerplus.sensor import SpielerPlusSensor
from custom_components.spielerplus.button import SpielerPlusRefresh
from custom_components.spielerplus.calendar import SpielerPlusCalendar
from custom_components.spielerplus.binary_sensor import SpielerPlusConnection

logging.disable(logging.CRITICAL)


class Response:
    status = 200

    def __init__(self, chunks):
        self.chunks = chunks
        self.content = self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def iter_chunked(self, size):
        for chunk in self.chunks:
            yield chunk


class Session:
    def __init__(self, chunks):
        self.chunks = chunks

    def get(self, *args, **kwargs):
        return Response(self.chunks)


class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_minute_callback_runs_in_event_loop(self):
        captured = []
        seen = []

        def track(hass, action, interval):
            captured.append(action)
            return lambda: None

        with (
            patch.object(
                integration, "SpielerPlusCoordinator", return_value=self.coordinator
            ),
            patch.object(
                self.coordinator, "async_config_entry_first_refresh", new=AsyncMock()
            ),
            patch.object(
                self.hass,
                "config_entries",
                new=SimpleNamespace(async_forward_entry_setups=AsyncMock()),
            ),
            patch.object(integration, "async_track_time_interval", side_effect=track),
            patch.object(
                self.coordinator,
                "async_update_listeners",
                side_effect=lambda: seen.append(asyncio.get_running_loop()),
            ),
        ):
            await integration.async_setup_entry(self.hass, self.entry)
            self.assertEqual(HassJob(captured[0]).job_type, HassJobType.Callback)
            captured[0](dt_util.utcnow())
            await self.hass.async_block_till_done()
        self.assertEqual(seen, [asyncio.get_running_loop()])

    async def asyncSetUp(self):
        self.directory = TemporaryDirectory()
        self.hass = HomeAssistant(self.directory.name)
        self.entry = ConfigEntry(
            version=1,
            minor_version=1,
            domain="spielerplus",
            title="Fixture",
            data={
                "name": "Fixture",
                "url": "https://www.spielerplus.de/events/ics?t=EXAMPLE&u=EXAMPLE",
            },
            options={},
            source="user",
            unique_id=None,
            discovery_keys=MappingProxyType({}),
            subentries_data=[],
        )
        self.coordinator = module.SpielerPlusCoordinator(self.hass, self.entry)
        self.start = (dt_util.utcnow() + timedelta(days=1)).replace(microsecond=0)
        self.raw = (
            "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Test//EN\r\nBEGIN:VEVENT\r\nUID:stable\r\nDTSTART:"
            + self.start.strftime("%Y%m%dT%H%M%SZ")
            + "\r\nDTEND:"
            + (self.start + timedelta(hours=1)).strftime("%Y%m%dT%H%M%SZ")
            + "\r\nSUMMARY:Training\r\nLOCATION:Demo\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
        ).encode()

    async def asyncTearDown(self):
        await self.hass.async_stop()
        self.directory.cleanup()

    async def fetch(self, raw):
        with patch.object(
            module,
            "async_get_clientsession",
            return_value=Session([raw[:40], raw[40:100], raw[100:]]),
        ):
            return await self.coordinator._async_update_data()

    async def test_chunked_read_and_initial_baseline(self):
        seen = []
        self.hass.bus.async_listen(
            "spielerplus_calendar_changed", lambda event: seen.append(event)
        )
        data = await self.fetch(self.raw)
        await self.hass.async_block_till_done()
        self.assertEqual(len(data), 1)
        self.assertEqual(seen, [])
        self.assertIsNotNone(self.coordinator.last_success)

    async def test_change_event_and_unchanged_refresh(self):
        self.coordinator.data = await self.fetch(self.raw)
        seen = []
        self.hass.bus.async_listen(
            "spielerplus_calendar_changed", lambda event: seen.append(event.data)
        )
        await self.fetch(self.raw)
        await self.hass.async_block_till_done()
        self.assertEqual(seen, [])
        await self.fetch(self.raw.replace(b"LOCATION:Demo", b"LOCATION:New field"))
        await self.hass.async_block_till_done()
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0]["change"], "updated")
        self.assertIsNotNone(self.coordinator.last_change)

    async def test_size_limit_and_error_redaction(self):
        self.coordinator.data = await self.fetch(self.raw)
        previous = self.coordinator.data
        with patch.object(module, "MAX_ICS_BYTES", 20):
            with self.assertRaises(UpdateFailed):
                await self.fetch(self.raw)
        self.assertIs(self.coordinator.data, previous)
        with patch.object(
            module, "async_get_clientsession", side_effect=ValueError("PRIVATE_URL")
        ):
            with self.assertRaises(UpdateFailed) as raised:
                await self.coordinator._async_update_data()
        self.assertNotIn("PRIVATE_URL", str(raised.exception))

    async def test_entities_and_failure_diagnostics(self):
        self.coordinator.data = await self.fetch(self.raw)
        sensor = SpielerPlusSensor(
            self.coordinator, self.entry, "countdown", "mdi:timer-outline", None
        )
        self.assertTrue(1438 <= sensor.native_value <= 1440)
        self.assertEqual(sensor.extra_state_attributes["location"], "Demo")
        calendar = SpielerPlusCalendar(self.coordinator, self.entry)
        self.assertEqual(calendar.unique_id, self.entry.entry_id)
        self.assertEqual(
            len(
                await calendar.async_get_events(
                    self.hass, dt_util.utcnow(), self.start + timedelta(days=1)
                )
            ),
            1,
        )
        self.coordinator.last_update_success = False
        self.assertFalse(sensor.available)
        self.assertTrue(SpielerPlusConnection(self.coordinator, self.entry).available)
        self.assertFalse(SpielerPlusConnection(self.coordinator, self.entry).is_on)
        diagnostic = SpielerPlusSensor(
            self.coordinator, self.entry, "last_success", "mdi:cloud", None
        )
        self.assertTrue(diagnostic.available)
        self.assertIsNotNone(diagnostic.native_value)

    async def test_premium_placeholder_has_no_events_and_explicit_diagnostic(self):
        self.coordinator.data = await self.fetch(
            self.raw.replace(b"SUMMARY:Training", b"SUMMARY:Premium-Feature")
        )
        self.assertEqual(self.coordinator.data, [])
        self.assertEqual(self.coordinator.calendar_notice, "calendar_premium_required")
        self.coordinator.last_update_success = True
        calendar = SpielerPlusCalendar(self.coordinator, self.entry)
        self.assertFalse(calendar.available)
        connection = SpielerPlusConnection(self.coordinator, self.entry)
        self.assertFalse(connection.is_on)
        self.assertEqual(
            connection.extra_state_attributes["last_error"], "calendar_premium_required"
        )
        self.assertTrue(SpielerPlusRefresh(self.coordinator, self.entry).available)
        self.coordinator.data = await self.fetch(self.raw)
        self.assertIsNone(self.coordinator.calendar_notice)
        self.assertTrue(calendar.available)

    async def test_refresh_button_requests_coordinator(self):
        self.coordinator.async_request_refresh = AsyncMock()
        await SpielerPlusRefresh(self.coordinator, self.entry).async_press()
        self.coordinator.async_request_refresh.assert_awaited_once()


if __name__ == "__main__":
    unittest.main(verbosity=2)
