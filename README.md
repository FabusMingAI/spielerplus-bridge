# SpielerPlus Bridge

Unofficial, read-only **SpielerPlus Premium calendar** bridge for Home Assistant and MCP. This project is not affiliated with SpielerPlus.

**Status: experimental pre-release.** Test on Raspberry Pi `mireia` before installing on the production Home Assistant instance.

## Components

- `custom_components/spielerplus`: Home Assistant custom calendar integration with UI config flow, multiple subscriptions and cached reads.
- `spielerplus_mcp`: Python MCP server with stdio tools `list_teams` and `list_events`.
- `tests`: parsing and security regression tests.

## Getting the calendar subscription

In SpielerPlus Premium: **Termine → Terminliste → Kalender → Kalender abonnieren**. Use your private `webcal://www.spielerplus.de/events/ics?...` URL. For the MCP environment you may replace the `webcal://` prefix with `https://`.

**Keep the complete ICS URL private.** It grants access to personal calendar data. Never commit, publish or paste it into an issue. Check [SECURITY.md](SECURITY.md).

## MCP server setup (Python 3.11+)

```bash
git clone https://github.com/FabusMingAI/spielerplus-bridge.git
cd spielerplus-bridge
python3 -m venv .venv
. .venv/bin/activate
pip install -r spielerplus_mcp/requirements.txt
# Set your secret URL privately in the shell/MCP host (never commit it)
export SPIELERPLUS_CALENDARS='{"Demo":"https://www.spielerplus.de/events/ics?t=EXAMPLE&u=EXAMPLE"}'
python -m spielerplus_mcp.server
```

Replace EXAMPLE values only in your **private** environment. Server uses MCP **stdio**, not a remote, authenticated HTTPS endpoint; ChatGPT cannot connect to this directly without an authenticated gateway.

## Home Assistant setup

On the **test** Home Assistant system first, copy `custom_components/spielerplus` into `/config/custom_components/spielerplus` and restart. Open **Settings → Devices & services → Add integration → SpielerPlus Calendar**. Add a display name and a private ICS link. Repeat for more team calendars. This repository may also be added as a **custom** HACS integration repository; it is not in HACS default.

## Tests

```bash
pip install -r spielerplus_mcp/requirements.txt pytest
pytest -q
```

See [ROADMAP.md](ROADMAP.md). RSVP/attendance writing is **not supported** by the ICS subscription.
