"""Read-only SpielerPlus MCP server over stdio."""
import json
import logging
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
from mcp.server.fastmcp import FastMCP

from .feeds import MAX_ICS_BYTES, parse_events, validate_url

mcp = FastMCP("SpielerPlus Calendar")
# HTTPX logs complete request URLs at INFO, including private ICS credentials.
logging.getLogger("httpx").setLevel(logging.WARNING)
TZ = ZoneInfo(os.getenv("SPIELERPLUS_TIMEZONE", "Europe/Berlin"))


def feeds():
    value = json.loads(os.environ.get("SPIELERPLUS_CALENDARS", "{}"))
    if not isinstance(value, dict):
        raise ValueError("SPIELERPLUS_CALENDARS must be a JSON object")
    if len(value) > 30:
        raise ValueError("Too many configured calendar feeds")
    return {
        name: validate_url(url)
        for name, url in value.items()
        if isinstance(name, str) and isinstance(url, str) and name.strip()
    }


def load_events(team: str, url: str, start: datetime, end: datetime):
    with httpx.Client(timeout=20, follow_redirects=False) as client:
        with client.stream("GET", url) as response:
            response.raise_for_status()
            if response.status_code != 200:
                raise ValueError("Unexpected HTTP response")
            chunks, total = [], 0
            for chunk in response.iter_bytes():
                total += len(chunk)
                if total > MAX_ICS_BYTES:
                    raise ValueError("Calendar feed too large")
                chunks.append(chunk)
    return parse_events(b"".join(chunks), start, end, team, TZ)


@mcp.tool()
def list_teams() -> list[str]:
    """List configured SpielerPlus team calendars."""
    return sorted(feeds())


@mcp.tool()
def list_events(days_ahead: int = 30, team: str = "") -> list[dict]:
    """List upcoming training sessions, matches and calendar events."""
    days_ahead = max(1, min(int(days_ahead), 365))
    now = datetime.now(TZ)
    configured = feeds()
    if team:
        if team not in configured:
            raise ValueError("Unknown team")
        configured = {team: configured[team]}
    result = []
    for name, url in configured.items():
        result.extend(load_events(name, url, now, now + timedelta(days=days_ahead)))
    return sorted(result, key=lambda event: event["start"])


if __name__ == "__main__":
    mcp.run(transport="stdio")
