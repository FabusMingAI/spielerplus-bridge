# Family dashboard / Familienansicht

## Deutsch

1. Den ersten Kalender einrichten. Unter **Konfigurieren → SpielerPlus-Konto verbinden** optional anmelden und die zum Kalender passende Mitgliedschaft wählen.
2. Für jedes weitere Kind **Dienst hinzufügen → Weiteres Kind mit vorhandenem Konto** wählen. Bei mehreren gespeicherten Konten die Quelle auswählen, danach die Mitgliedschaft des Kindes.
3. Ein eindeutig erkennbarer offizieller Kalenderlink wird im Hintergrund übernommen. Andernfalls den privaten Link dieser Mitgliedschaft direkt in Home Assistant eintragen. Einen fremden Kind-Kalender nicht ersatzweise verwenden. Anzeigenamen prüfen und speichern.
4. Unter **Entwicklerwerkzeuge → Aktionen** `spielerplus.rebuild_dashboard` ausführen. Die Integration erzeugt `/config/spielerplus-family.yaml` anhand der tatsächlichen Entitäts-IDs.
5. In `configuration.yaml` den folgenden Dashboard-Eintrag zum vorhandenen `lovelace.dashboards` ergänzen und Home Assistant neu starten:

```yaml
lovelace:
  dashboards:
    spielerplus-family:
      mode: yaml
      title: SpielerPlus Familie
      icon: mdi:account-group
      show_in_sidebar: true
      filename: spielerplus-family.yaml
```

Die Übersicht zeigt die nächsten Trainings/Spiele je Kind und eine gemeinsame, zeitlich sortierte Sportwoche. Jedes Kind hat einen eigenen Tab mit Kalender und Diagnose. Die Texte der generierten Ansicht sind deutsch.

**Dateischutz:** Die Aktion ersetzt ausschließlich eine fehlende Datei oder eine mit dem SpielerPlus-Verwaltungsmarker beginnende Datei. Bestehende eigene Dateien und symbolische Links bleiben erhalten. Eine bereits verwaltete Datei wird beim Laden eines Eintrags automatisch aktualisiert. Nach dem Entfernen eines Eintrags oder Umbenennen von Entitäten die Aktion erneut ausführen. Für eigene Anpassungen die Datei unter einem anderen Namen kopieren und separat registrieren.

**Anmeldung:** Die Zugangsdaten werden in jeden Kind-Eintrag kopiert; nach einer Passwortänderung alle betroffenen Einträge aktualisieren. Sitzungen sind getrennt. Dasselbe Kalenderabonnement ist für unterschiedliche Mitgliedschaften zulässig; dieselbe Kombination wird als Duplikat abgewiesen. Die gewählte Mitgliedschaft muss trotzdem zum Kalender passen. Die Teilnahmedaten werden ausschließlich anhand offizieller Terminlinks zugeordnet. Ihre Abdeckung bleibt auf die ersten fünf aufgelisteten Termine je Mitgliedschaft begrenzt.

## English

1. Set up the first calendar and optionally use **Configure → Connect SpielerPlus account**. Select the membership matching that calendar.
2. Choose **Add service → Another child using an existing account**, select the credential source if needed, then the child's membership.
3. A uniquely discoverable official calendar subscription is used in the background. Otherwise enter that child's private link directly in Home Assistant. Verify the display name and save.
4. Run `spielerplus.rebuild_dashboard` under **Developer tools → Actions**. It writes `/config/spielerplus-family.yaml` using actual registered entity IDs.
5. Add the YAML registration shown above to your existing `lovelace.dashboards` configuration and restart Home Assistant.

The overview combines next training/game cards and a chronological sports week, with an individual calendar/diagnostic tab per child. Generated dashboard text is German.

**File protection:** Only a missing file or a file starting with the SpielerPlus management marker can be written. Existing unowned files and symlinks are preserved. A managed dashboard updates when an entry loads. Rebuild after removing an entry or renaming entities. For custom edits, copy it to another filename and register that copy separately.

**Sign-in:** Credentials are copied into each child's local entry; update each affected entry after a password change. Sessions are isolated. Different memberships may share one subscription; the same membership/subscription pair is rejected as a duplicate. Make sure each membership corresponds to its calendar. Attendance is matched only by official event links and covers the first five listed events per membership.

## Kalenderabonnement / Calendar subscription

Liefert SpielerPlus statt Terminen nur einen „Premium-Feature“-Platzhalter, zeigt die Integration `calendar_premium_required`. Der Platzhalter wird nicht als echter Termin gezählt. Die Kalenderentitäten sind nicht verfügbar, Diagnose und Aktualisieren bleiben bedienbar. Premium-/Abonnementberechtigung für diese Mitgliedschaft bei SpielerPlus prüfen.

When the provider returns only a “Premium-Feature” placeholder, the integration reports `calendar_premium_required`, excludes the placeholder from events and marks calendar entities unavailable. Diagnostics and refresh remain accessible. Check the subscription/Premium entitlement for that membership with SpielerPlus.
