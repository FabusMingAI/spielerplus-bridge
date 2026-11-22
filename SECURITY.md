# Security

The complete SpielerPlus ICS URL contains **bearer credentials**. Anyone with it may be able to read calendar information.

- Never commit, paste into public issues or log the real ICS URL.
- Store MCP URLs in a private environment variable (SPIELERPLUS_CALENDARS).
- Store Home Assistant URLs through the integration config flow and protect backups.
- Do not expose an unauthenticated stdio MCP process as a public web service.
- Only the exact official HTTPS ICS host and endpoint are accepted; HTTP redirects are disabled.
- The bridge is **read-only**. No team membership or RSVP modifications.
- If a live URL has been exposed, regenerate it in SpielerPlus if the service allows.

Please report vulnerabilities without including live links.
