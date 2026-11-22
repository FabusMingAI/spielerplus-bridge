"""Optional authenticated HTML adapter with no RSVP-write implementation."""

import asyncio
import json
from urllib.parse import urlparse

import aiohttp

from .attendance import (
    BASE,
    MAX_HTML_BYTES,
    AccountError,
    event_summaries,
    login_form,
    memberships,
    official_url,
    participation_counts,
)

from .config_helpers import calendar_subscription

GET_PATHS = {
    "/site/login",
    "/site/select-team",
    "/site/switch-user",
    "/dashboard",
    "/dashboard/index",
    "/events",
    "/events/index",
    "/events/calendar",
}
POST_PATHS = {"/site/login", "/events/ajaxgetparticipation"}


class SpielerPlusAccount:
    def __init__(self, email, password, membership_id=None):
        self._email, self._password = email, password
        self.membership_id = str(membership_id) if membership_id is not None else None
        if self.membership_id is not None and not self.membership_id.isdigit():
            raise AccountError("no_memberships")
        self._session = None
        self._authenticated = False
        self._auth_error = None

    async def async_close(self):
        if self._session is not None:
            await self._session.close()
            self._session = None
        self._authenticated = False

    async def _request(self, method, path, data=None):
        if method not in {"GET", "POST"}:
            raise AccountError("unexpected_response")
        url = official_url(path)
        if self._session is None:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=25),
                headers={
                    "User-Agent": "Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 SpielerPlusBridge/0.3",
                    "Accept-Language": "de-DE,de;q=0.9",
                },
            )
        try:
            for _ in range(6):
                parsed = urlparse(url)
                if parsed.path not in (GET_PATHS if method == "GET" else POST_PATHS):
                    raise AccountError(
                        "unsupported_login"
                        if "/site/" in parsed.path
                        else "unexpected_response"
                    )
                headers = {
                    "Referer": BASE
                    + (
                        "/site/login"
                        if parsed.path == "/site/login"
                        else "/events/index"
                    )
                }
                if parsed.path == "/events/ajaxgetparticipation":
                    headers["X-Requested-With"] = "XMLHttpRequest"
                async with self._session.request(
                    method, url, data=data, headers=headers, allow_redirects=False
                ) as response:
                    if response.status in {301, 302, 303}:
                        url = official_url(response.headers.get("Location", ""))
                        method, data = "GET", None
                        continue
                    if response.status in {307, 308}:
                        raise AccountError("unexpected_response")
                    if response.status == 403:
                        raise AccountError("access_denied")
                    if response.status == 401:
                        raise AccountError("invalid_auth")
                    if response.status != 200:
                        raise AccountError("cannot_connect")
                    chunks, total = [], 0
                    async for chunk in response.content.iter_chunked(64 * 1024):
                        total += len(chunk)
                        if total > MAX_HTML_BYTES:
                            raise AccountError("response_too_large")
                        chunks.append(chunk)
                    return b"".join(chunks).decode("utf-8", errors="replace"), urlparse(
                        url
                    ).path
            raise AccountError("unexpected_response")
        except (aiohttp.ClientError, TimeoutError, ValueError):
            raise AccountError("cannot_connect") from None

    async def async_login(self):
        if self._auth_error:
            raise AccountError(self._auth_error)
        try:
            html, path = await self._request("GET", "/site/login")
            if path == "/site/login":
                form = await asyncio.to_thread(login_form, html)
                values = dict(form.fields)
                values[form.email_field], values[form.password_field] = (
                    self._email,
                    self._password,
                )
                await self._request("POST", form.action, data=values)
            html, _ = await self._request("GET", "/site/select-team")
            choices = await asyncio.to_thread(memberships, html)
            if self.membership_id is not None:
                if self.membership_id not in choices:
                    raise AccountError("no_memberships")
                await self._request("GET", f"/site/switch-user?id={self.membership_id}")
            self._authenticated = True
            return choices
        except AccountError as exc:
            if exc.code in {
                "invalid_auth",
                "unsupported_login",
                "no_memberships",
                "access_denied",
            }:
                self._auth_error = exc.code
            raise

    async def async_fetch(self):
        if not self._authenticated:
            await self.async_login()
        html, path = await self._request("GET", "/events/index")
        if path == "/site/login":
            self._authenticated = False
            await self.async_login()
            html, _ = await self._request("GET", "/events/index")
        summaries, csrf = await asyncio.to_thread(event_summaries, html)
        for summary in summaries.values():
            payload = {
                "eventid": summary["event_id"],
                "eventtype": summary["event_type"],
            }
            if csrf[1]:
                payload[csrf[0]] = csrf[1]
            try:
                detail, _ = await self._request(
                    "POST", "/events/ajaxgetparticipation", data=payload
                )
                if detail.lstrip().startswith("{"):
                    parsed = json.loads(detail)
                    if not isinstance(parsed, dict) or not isinstance(
                        parsed.get("html"), str
                    ):
                        raise AccountError("unexpected_response")
                    detail = parsed["html"]
                counts, own = await asyncio.to_thread(
                    participation_counts, detail, self.membership_id
                )
                summary["counts"].update(
                    {key: value for key, value in counts.items() if value is not None}
                )
                if own is not None:
                    summary["own_status"] = own
            except (AccountError, ValueError) as exc:
                summary["detail_error"] = (
                    exc.code if isinstance(exc, AccountError) else "unexpected_response"
                )
        return summaries

    async def async_calendar_subscription(self):
        if not self._authenticated:
            await self.async_login()
        for path in ("/events/index", "/events/calendar"):
            try:
                html, _ = await self._request("GET", path)
                value = await asyncio.to_thread(calendar_subscription, html)
                if value:
                    return value
            except AccountError:
                continue
        return None
