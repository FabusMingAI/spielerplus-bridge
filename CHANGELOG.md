# Changelog / Änderungsprotokoll

## 0.2.0 — preview / Vorschau — 2026-11-22

### Added / Neu

- EN: Six sensors per subscription: next training, next game, countdown, next-seven-day count/list, last successful fetch and last change. Connection diagnostic and manual refresh button.
- DE: Sechs Sensoren pro Abonnement: nächstes Training, nächstes Spiel, Countdown, Anzahl/Liste der nächsten sieben Tage, letzter erfolgreicher Abruf und letzte Änderung. Verbindungsdiagnose und Aktualisieren-Button.
- EN: Shared coordinator, device grouping, English/German translations, status/coordinates/event links, quiet initial baseline and change events for upcoming appointments.
- DE: Gemeinsamer Abruf, Gerätezuordnung, deutsche/englische Übersetzungen, Status/Koordinaten/Terminlinks, stille Ausgangsbasis und Änderungsereignisse für kommende Termine.
- EN: Native-card dashboard template, automation examples, bilingual READMEs and screenshots with fictional data.
- DE: Dashboard-Vorlage mit Standardkarten, Automationsbeispiele, zweisprachige READMEs und Screenshots mit erfundenen Daten.

### Fixed / Behoben

- EN: Read the entire streamed ICS response with a cumulative size limit; a single stream read could truncate calendars. Preserve the original calendar unique ID.
- DE: Vollständiger Empfang gestreamter ICS-Antworten mit kumulativem Größenlimit; ein einzelner Leseaufruf konnte Kalender abschneiden. Die bisherige Kalender-Unique-ID bleibt erhalten.
- EN: Suppress HTTPX request INFO logs in the MCP server so they do not print private subscription URLs. Coordinator errors report only exception classes.
- DE: HTTPX-Request-Info-Logs im MCP-Server unterdrückt, damit private Abonnement-URLs dort nicht ausgegeben werden. Coordinator-Fehler nennen nur die Fehlerklasse.

### Limits / Grenzen

- EN: Read-only calendar data. No attendance/RSVP login or remote MCP gateway. The dashboard is manually registered. Change history is in memory and resets on restart/reload.
- DE: Lesende Kalenderanbindung. Kein Anwesenheits-/Zu-/Absage-Login und kein Remote-MCP-Gateway. Das Dashboard wird manuell registriert. Die Änderungshistorie liegt im Arbeitsspeicher und beginnt nach Neustart/Neuladen neu.

## 0.1.0 — initial source version / ursprüngliche Quellversion

- EN: Experimental Home Assistant calendar, UI setup, multiple subscriptions, local MCP stdio tools, URL validation, bounded downloads and parser/security tests.
- DE: Experimenteller HA-Kalender, UI-Einrichtung, mehrere Abonnements, lokale MCP-stdio-Werkzeuge, URL-Prüfung, begrenzte Downloads und Parser-/Sicherheitstests.
