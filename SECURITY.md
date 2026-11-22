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

## Optional account sign-in (v0.3.0 preview)

Email/password are stored in the local HA config entry options and can be included in HA backups. Never share `.storage`, account form contents, cookies, CSRF tokens or raw account HTML. Cookies stay in memory in an isolated client session. Active account options can be removed through Configure → Remove account sign-in; this does not erase older backups.

Entity state contains only own response, aggregate group counts, times and sanitized error codes. Participant names and absence reasons are not retained. The adapter has no RSVP-write endpoint. It does not automate additional authentication challenges or disable certificate verification. Account errors do not invalidate successful ICS fetches.

Family setup copies the existing credentials into each child's local config entry; sessions and membership context remain isolated. After changing a password, update each affected entry. Generated dashboards include private display names and entity IDs, so keep them local. They do not include passwords, membership IDs or subscription links.
