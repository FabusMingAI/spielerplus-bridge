"""Account transport and isolation tests; uses synthetic data only."""

import os, sys

sys.path.insert(0, os.environ.get("HA_CONFIG", "/config"))
from datetime import timedelta
from tempfile import TemporaryDirectory
from types import MappingProxyType
from unittest import IsolatedAsyncioTestCase, main
from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from custom_components.spielerplus.account import SpielerPlusAccount
from custom_components.spielerplus.attendance import AccountError
from custom_components.spielerplus import coordinator as module
from custom_components.spielerplus.sensor import SpielerPlusParticipation
from custom_components.spielerplus.binary_sensor import SpielerPlusAccountConnection

LOGIN = '<form action="/site/login"><input type="hidden" name="_csrf" value="DEMO_CSRF"><input type="email" name="email"><input type="password" name="password"></form>'
TEAMS = '<div class="select-team-item"><a href="/site/switch-user?id=999"></a><div class="select-team-item-meta"><h4>Demo Team</h4></div></div>'


class Content:
    def __init__(self, chunks):
        self.chunks = chunks

    async def iter_chunked(self, size):
        for chunk in self.chunks:
            yield chunk


class Response:
    def __init__(self, status=200, body=b"ok", headers=None):
        self.status = status
        self.headers = headers or {}
        self.content = Content([body[:1], body[1:]])

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


class Session:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.responses.pop(0)

    def get(self, *args, **kwargs):
        return Response(body=kwargs.pop("fixture"))

    async def close(self):
        pass


class AccountTests(IsolatedAsyncioTestCase):
    async def test_login_posts_only_to_validated_official_form(self):
        client = SpielerPlusAccount("demo@example.invalid", "FICTIONAL_PASSWORD", "999")
        client._request = AsyncMock(
            side_effect=[
                (LOGIN, "/site/login"),
                ("", "/site/select-team"),
                (TEAMS, "/site/select-team"),
                ("", "/dashboard/index"),
            ]
        )
        choices = await client.async_login()
        self.assertEqual(choices, {"999": "Demo Team"})
        calls = client._request.call_args_list
        self.assertEqual(
            calls[1].args, ("POST", "https://www.spielerplus.de/site/login")
        )
        self.assertEqual(calls[1].kwargs["data"]["_csrf"], "DEMO_CSRF")
        self.assertEqual(calls[1].kwargs["data"]["password"], "FICTIONAL_PASSWORD")

    async def test_rejected_credentials_are_not_retried_each_poll(self):
        client = SpielerPlusAccount("demo@example.invalid", "FICTIONAL_PASSWORD")
        client._request = AsyncMock(side_effect=AccountError("invalid_auth"))
        for _ in range(2):
            with self.assertRaises(AccountError):
                await client.async_login()
        self.assertEqual(client._request.await_count, 1)

    async def test_existing_private_session_can_recover_without_posting_password(self):
        client = SpielerPlusAccount("demo@example.invalid", "FICTIONAL_PASSWORD")
        client._request = AsyncMock(
            side_effect=[("", "/dashboard/index"), (TEAMS, "/site/select-team")]
        )
        await client.async_login()
        self.assertTrue(all(c.args[0] == "GET" for c in client._request.call_args_list))

    async def test_foreign_redirect_never_receives_credentials(self):
        client = SpielerPlusAccount("demo@example.invalid", "FICTIONAL_PASSWORD")
        session = Session(
            Response(302, headers={"Location": "https://evil.example/capture"})
        )
        client._session = session
        with self.assertRaises(AccountError):
            await client._request(
                "POST", "/site/login", data={"password": "FICTIONAL_PASSWORD"}
            )
        self.assertEqual(len(session.calls), 1)
        self.assertEqual(session.calls[0][1], "https://www.spielerplus.de/site/login")

    async def test_login_redirect_drops_post_body(self):
        client = SpielerPlusAccount("demo@example.invalid", "FICTIONAL_PASSWORD")
        session = Session(
            Response(302, headers={"Location": "/site/select-team"}), Response()
        )
        client._session = session
        await client._request(
            "POST", "/site/login", data={"password": "FICTIONAL_PASSWORD"}
        )
        self.assertEqual(session.calls[1][0], "GET")
        self.assertIsNone(session.calls[1][2]["data"])

    async def test_no_rsvp_write_endpoint_or_method_exists(self):
        client = SpielerPlusAccount("demo@example.invalid", "FICTIONAL_PASSWORD")
        session = Session()
        client._session = session
        for method, path in [
            ("POST", "/events/ajaxsaveparticipation"),
            ("DELETE", "/events/index"),
            ("POST", "/training/update"),
        ]:
            with self.assertRaises(AccountError):
                await client._request(method, path)
        self.assertEqual(session.calls, [])

    async def test_total_html_limit_and_sanitized_failures(self):
        client = SpielerPlusAccount("demo@example.invalid", "FICTIONAL_PASSWORD")
        client._session = Session(Response(body=b"a" * 50))
        with patch("custom_components.spielerplus.account.MAX_HTML_BYTES", 10):
            with self.assertRaises(AccountError) as error:
                await client._request("GET", "/events/index")
        self.assertEqual(str(error.exception), "response_too_large")
        client._session = Session(Response(403))
        with self.assertRaises(AccountError) as error:
            await client._request("GET", "/events/index")
        self.assertEqual(str(error.exception), "access_denied")

    async def test_account_failure_leaves_calendar_healthy_and_old_counts_unavailable(
        self,
    ):
        with TemporaryDirectory() as directory:
            hass = HomeAssistant(directory)
            entry = ConfigEntry(
                version=1,
                minor_version=1,
                domain="spielerplus",
                title="Demo",
                data={
                    "name": "Demo",
                    "url": "https://www.spielerplus.de/events/ics?t=EXAMPLE&u=EXAMPLE",
                },
                options={},
                source="user",
                unique_id=None,
                discovery_keys=MappingProxyType({}),
                subentries_data=[],
            )
            coordinator = module.SpielerPlusCoordinator(hass, entry)
            coordinator.account_client = type(
                "FakeAccount",
                (),
                {"async_fetch": AsyncMock(side_effect=AccountError("invalid_auth"))},
            )()
            start = dt_util.utcnow() + timedelta(days=1)
            raw = (
                "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:demo\r\nDTSTART:"
                + start.strftime("%Y%m%dT%H%M%SZ")
                + "\r\nDTEND:"
                + (start + timedelta(hours=1)).strftime("%Y%m%dT%H%M%SZ")
                + "\r\nSUMMARY:Training\r\nURL:https://www.spielerplus.de/training/view?id=101\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
            ).encode()

            class CalendarSession:
                def get(self, *args, **kwargs):
                    return Response(body=raw)

            with patch.object(
                module, "async_get_clientsession", return_value=CalendarSession()
            ):
                coordinator.data = await coordinator._async_update_data()
            self.assertEqual(len(coordinator.data), 1)
            self.assertIsNotNone(coordinator.last_success)
            self.assertEqual(coordinator.account_error, "invalid_auth")
            sensor = SpielerPlusParticipation(coordinator, entry, "training")
            self.assertFalse(sensor.available)
            self.assertFalse(SpielerPlusAccountConnection(coordinator, entry).is_on)
            coordinator.account_error = None
            coordinator.account_last_success = dt_util.utcnow()
            coordinator.participation = {
                "training:101": {
                    "own_status": "accepted",
                    "counts": {"accepted": 12, "pending": None},
                    "times": {"meeting_time": "17:45", "start_time": "18:00"},
                    "detail_error": None,
                }
            }
            self.assertTrue(sensor.available)
            self.assertEqual(sensor.native_value, "accepted")
            self.assertIsNone(sensor.extra_state_attributes["counts"]["pending"])
            self.assertEqual(sensor.extra_state_attributes["start_time"], "18:00")
            await hass.async_stop()


if __name__ == "__main__":
    main(verbosity=2)
