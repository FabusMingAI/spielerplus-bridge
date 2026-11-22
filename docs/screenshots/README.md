# Screenshot fixtures

The public images are genuine Home Assistant screenshots of the dashboard template,
rendered with **fictional entities and appointments**. No real team, child, account
identifier, private calendar URL or exported ICS file is included. The screenshots use the browser's default viewport at capture time;
no viewport override is required. No third-party frontend cards are required.

- `../images/dashboard-family.jpg`: two fictional children, Lea and Ben, with isolated responses and a shared sports week.
- `family-fixtures.yaml`: reproducible fictional entities for both children.
- `../images/dashboard-overview.jpg`: next training/game, countdown and sports week.
- `../images/dashboard-attendance.jpg`: fictional own responses, counts and meeting/start times.
- `../images/account-setup.jpg`: the empty local account dialog, captured before credentials were entered.
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

## Family screenshot

Use `family-fixtures.yaml` instead of the single-child template include. Generate a demo dashboard with `build_family_dashboard` from `custom_components/spielerplus/dashboard.py`, passing only fictional entry IDs/names and the `spielerplus_demo_*` / `spielerplus_demo2_*` entity IDs. Register it as a separate YAML dashboard. Do not run the registry-based rebuild action for public screenshots: that would use real child names. Capture the family overview with the sidebar collapsed; remove the demo registration and template include afterward.
