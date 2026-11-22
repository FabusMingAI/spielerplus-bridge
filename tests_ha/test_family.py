"""Family config flows and templates with fictional entries only."""

import os, sys

sys.path.insert(0, os.environ.get("HA_CONFIG", "/config"))
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase, main
from unittest.mock import AsyncMock, MagicMock, patch
import json
from datetime import datetime
from jinja2.sandbox import SandboxedEnvironment
from homeassistant.core import HomeAssistant
from custom_components.spielerplus.config_flow import (
    SpielerPlusConfigFlow,
    reuse_account,
)
from custom_components.spielerplus.dashboard import build_family_dashboard

URL = "https://www.spielerplus.de/events/ics?t=EXAMPLE&u=EXAMPLE"


class FamilyTests(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = TemporaryDirectory()
        self.hass = HomeAssistant(self.directory.name)

    async def asyncTearDown(self):
        await self.hass.async_stop()
        self.directory.cleanup()

    def flow(self, member=None):
        flow = SpielerPlusConfigFlow()
        flow.hass = self.hass
        flow.async_set_unique_id = AsyncMock()
        flow._abort_if_unique_id_configured = MagicMock()
        flow._async_current_entries = MagicMock(
            return_value=[
                SimpleNamespace(data={"url": URL}, options={"membership_id": "101"})
            ]
        )
        if member:
            flow._family_options = {
                "account_email": "demo@example.invalid",
                "account_password": "FICTIONAL_PASSWORD",
                "membership_id": member,
            }
        return flow

    async def test_same_feed_new_membership_is_created_with_separate_options(self):
        flow = self.flow("202")
        result = await flow.async_step_calendar({"name": "Ben", "url": URL})
        self.assertEqual(result["type"], "create_entry")
        self.assertEqual(result["options"]["membership_id"], "202")
        self.assertEqual(result["data"]["child_name"], "Ben")
        self.assertNotIn(URL, flow.async_set_unique_id.await_args.args[0])

    async def test_duplicate_membership_or_calendar_only_is_rejected(self):
        for member in ["101", None]:
            result = await self.flow(member).async_step_calendar(
                {"name": "Demo", "url": URL}
            )
            self.assertEqual(result["type"], "abort")
            self.assertEqual(result["reason"], "already_configured")

    async def test_detected_private_url_never_appears_in_form(self):
        flow = self.flow("202")
        flow._detected_url = URL
        flow._family_name = "Ben"
        result = await flow.async_step_calendar()
        self.assertNotIn(
            "url", [str(key.schema) for key in result["data_schema"].schema]
        )
        self.assertNotIn(URL, str(result))
        result = await flow.async_step_calendar({"name": "Ben"})
        self.assertEqual(result["data"]["url"], URL)

    async def test_empty_display_name_is_not_saved(self):
        result = await self.flow("202").async_step_calendar({"name": "   ", "url": URL})
        self.assertEqual(result["errors"], {"base": "invalid_name"})

    async def test_reuse_copies_only_credentials_and_closes_temporary_session(self):
        source = SimpleNamespace(
            options={
                "account_email": "demo@example.invalid",
                "account_password": "FICTIONAL_PASSWORD",
                "membership_id": "101",
                "irrelevant": "NOT_COPIED",
            }
        )
        client = SimpleNamespace(
            async_login=AsyncMock(return_value={"202": "Demo · Ben"}),
            async_close=AsyncMock(),
        )
        with patch(
            "custom_components.spielerplus.account.SpielerPlusAccount",
            return_value=client,
        ):
            credentials, choices = await reuse_account(source)
        self.assertEqual(set(credentials), {"account_email", "account_password"})
        self.assertEqual(choices, {"202": "Demo · Ben"})
        client.async_close.assert_awaited_once()

    async def test_family_templates_keep_children_separate_and_sort_events(self):
        children = [
            {
                "entry_id": key,
                "name": name,
                "entities": {
                    "next_training": f"sensor.{key}_next_training",
                    "next_game": f"sensor.{key}_next_game",
                    "events_week": f"sensor.{key}_week",
                    "training_participation": f"sensor.{key}_participation",
                    "account_connection": f"binary_sensor.{key}_account",
                },
            }
            for key, name in [("lea", "Lea"), ("ben", "Ben")]
        ]
        result = build_family_dashboard(children)
        env = SandboxedEnvironment()
        env.globals.update(
            states=lambda entity: (
                "on"
                if entity.startswith("binary_sensor.")
                else "2026-11-23T18:00:00+01:00"
            ),
            is_state=lambda *args: True,
            as_timestamp=lambda value: datetime.fromisoformat(value).timestamp(),
        )

        def attrs(entity, key):
            if key == "events":
                return [
                    {
                        "title": entity,
                        "start": "2026-11-23T18:00:00+01:00",
                        "location": "Demo",
                    }
                ]
            if key == "counts":
                return {
                    "accepted": 2,
                    "uncertain": 0,
                    "declined": 1,
                    "pending": None,
                    "not_nominated": 0,
                }
            return "Demo"

        env.globals["state_attr"] = attrs
        env.filters["timestamp_custom"] = lambda value, format: "Demo time"

        def render_cards(node):
            if isinstance(node, dict):
                if node.get("type") == "markdown":
                    env.from_string(node["content"]).render()
                for value in node.values():
                    render_cards(value)
            elif isinstance(node, list):
                for value in node:
                    render_cards(value)

        render_cards(result)
        self.assertNotIn("sensor.ben_", json.dumps(result["views"][1]))
        self.assertNotIn("sensor.lea_", json.dumps(result["views"][2]))


if __name__ == "__main__":
    main(verbosity=2)
