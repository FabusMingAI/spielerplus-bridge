# Attendance and RSVP — research / Recherche

Checked / geprüft: 2026-11-22.

## What the calendar can provide

The inspected subscription provides standard event fields, including title, start/end, description, location, status, event URL and, for some events, coordinates. It does not provide structured participant lists or RSVP state. `STATUS` describes an event, not the user's attendance response. No private calendar content is stored in this repository.

## Evidence for a separate access path

The independent [spielerplus-anytype-sync project](https://github.com/LucaBaur/spielerplus-anytype-sync) documents logging into the web application, selecting a team and reading participation through `/events/ajaxgetparticipation`. This is a feasibility lead from that project's documentation, not an official or supported API contract. Its documented login assumes no 2FA; we have not tested compatibility with the user's account or independently validated the endpoint. No code from that project has been copied.

An official publicly documented attendance API was not confirmed during this research. That does not prove that no partner/private API exists. A provider-supported interface remains preferable if available.

## Proposed next milestone

1. Inspect attendance in the user's own authorized web session without changing an RSVP.
2. Confirm visible fields, team permissions, event identifiers, pagination and authentication behavior, including 2FA.
3. Build a separate optional, read-only account adapter with bounded requests, sanitized errors and fixture-based parser tests. Keep calendar-only setup usable without an account login.
4. Add own attendance and aggregate counts before considering participant names. Distinguish missing permission, unknown state and zero participants.
5. Consider write actions separately, with explicit selection of the event and response. Never infer or submit an RSVP from calendar attendance alone.

No login credentials, account adapter or RSVP write actions are part of v0.2.0.

## Deutsch

Der Kalender liefert keine strukturierten Zu-/Absagen oder Teilnehmerlisten. Ein separates Community-Projekt dokumentiert einen angemeldeten Webzugriff auf Teilnahmedaten. Das macht eine spätere Erweiterung technisch plausibel, ist aber keine offizielle Schnittstellenzusage und wurde mit diesem Konto noch nicht geprüft.

Als nächsten Schritt zuerst die eigenen sichtbaren Teilnahmedaten lesend untersuchen, Berechtigungen und Anmeldung klären und danach einen optionalen Konto-Adapter entwickeln. Die Kalenderanbindung soll ohne Kontoanmeldung weiter funktionieren. Schreibende Zu-/Absagen wären ein gesonderter Ausbau.
