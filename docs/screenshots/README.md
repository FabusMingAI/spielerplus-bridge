# Screenshot fixtures

The public images are genuine Home Assistant screenshots of the dashboard template,
rendered with **fictional entities and appointments**. No real team, child, account
identifier, private calendar URL or exported ICS file is included. The current
screenshots use the browser's default portrait viewport; they do not claim a
separate desktop-device test. No third-party frontend cards are required.

- `../images/dashboard-overview.jpg`: next training/game, countdown and sports week.
- `../images/dashboard-status.jpg`: an example moved match and connection diagnostics.
- `template-fixtures.yaml`: Home Assistant template entities with synthetic values.
  The `from_json` templates preserve list/dictionary attributes used by the dashboard.
  Fixture dates are intentionally fixed to make the captured example reproducible.

## Regenerate in an isolated test instance

1. Copy `template-fixtures.yaml` into the HA config directory as
   `spielerplus-demo-template.yaml` and add:

   ```yaml
   template: !include spielerplus-demo-template.yaml
   input_button:
     spielerplus_demo_refresh:
       name: Demo aktualisieren
   ```

2. Copy `dashboard/spielerplus.yaml` into that instance. Its placeholder sensor IDs
   already match the fixtures. For the refresh control only, replace
   `button.spielerplus_demo_refresh` with `input_button.spielerplus_demo_refresh`
   and `perform_action: button.press` with `perform_action: input_button.press`.
3. Register the copied file as a separate YAML dashboard. Set the heading to
   `Demo · SV Beispiel U15`. Validate configuration, then restart.
4. Open both views, check all values and capture screenshots at the browser's
   default size. Review the images visually before publishing. Exclude browser
   chrome and account/profile sidebars.
5. Remove the screenshot-only template/include, input button and demo dashboard
   registration and restart. Leave the user's real integration/data unchanged.

The fixture button only records a demo press. The real integration's refresh
button is separately tested against the coordinator by the runtime test suite.
