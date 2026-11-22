# Development and releases

## Local parser tests

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
python scripts/validate_repository.py
python -m pytest -q
python -m compileall -q spielerplus_mcp custom_components tests tests_ha
```

`tests/test_calendar_events.py` loads the pure event module without importing the Home Assistant lifecycle. It checks timezone/all-day handling, recurrence identity, moved events, cancellation, metadata, link filtering, truncated data and rolling comparison windows. Existing tests cover the MCP feed and configuration.

## Home Assistant runtime tests

Install `custom_components/spielerplus` in an isolated Home Assistant test container and let its requirements install. Then run:

```bash
docker cp tests_ha/test_runtime.py CONTAINER:/tmp/test_spielerplus.py
docker exec CONTAINER python /tmp/test_spielerplus.py
docker cp tests_ha/test_account.py CONTAINER:/tmp/test_account.py
docker exec CONTAINER python /tmp/test_account.py
```

These standard-library unittest tests exercise bounded chunked downloads, coordinator change events, initial-baseline behavior, sanitized errors, diagnostic availability, calendar identity and the manual-refresh button. They use synthetic responses and do not require a real subscription.

## Screenshots

See [docs/screenshots/README.md](docs/screenshots/README.md). Public screenshots must use fictional fixtures, never a real team, child, private subscription URL or exported calendar.

## Release checklist

1. Update the manifest version, changelog and both READMEs together. Describe unsupported capabilities and required manual steps.
2. Run parser tests, runtime tests and configuration validation. Test the dashboard on desktop and mobile sizes in an isolated instance.
3. Check relative documentation links, JSON/YAML syntax and private-URL scans; review every staged file, including images.
4. Open a pull request, wait for CI and review the final source diff.
5. After merging, tag the reviewed commit and publish a GitHub Release using `docs/releases/vX.Y.Z.md`. Update preview wording/badges when the release is actually published.

Never include `.storage`, `.env`, test-instance configuration, raw ICS exports or real-calendar screenshots in a release.
