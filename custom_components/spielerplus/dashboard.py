"""Generate a credential-free family dashboard from registered entry entities."""

import json
import re
from hashlib import sha256
from pathlib import Path

MARKER = "# Managed by SpielerPlus Bridge. Rebuild replaces this file.\n"
FILENAME = "spielerplus-family.yaml"
ROLES = {
    "calendar",
    "next_training",
    "next_game",
    "countdown",
    "events_week",
    "last_success",
    "last_change",
    "connection",
    "refresh",
    "training_participation",
    "game_participation",
    "account_last_success",
    "account_connection",
}
ENTITY_ID = re.compile(r"^[a-z_]+\.[a-z0-9_]+$")


def heading(name, icon="mdi:account-child"):
    return {"type": "heading", "heading": name, "heading_style": "title", "icon": icon}


def quote(value):
    return json.dumps(value, ensure_ascii=True)


def next_card(entities, key, label):
    entity = entities.get(key)
    if not entity:
        return {
            "type": "markdown",
            "content": f"## {label}\n\nDie Entitäten werden noch eingerichtet.",
        }
    kind = "training" if key == "next_training" else "game"
    participation = entities.get(kind + "_participation", "")
    connection = entities.get("account_connection", "")
    text = """{% set e = ENTITY %}
## LABEL

{% if states(e) not in ['unknown','unavailable'] %}
**{{ as_timestamp(states(e)) | timestamp_custom('%d.%m.%Y · %H:%M') }}**

{{ state_attr(e,'title') or '' }}

Ort: {{ state_attr(e,'location') or 'noch offen' }}
{% else %}
Kein aktueller Termin verfügbar.
{% endif %}
""".replace("ENTITY", quote(entity)).replace("LABEL", label)
    if participation and connection:
        text += """
{% set p = PARTICIPATION %}
{% set live = is_state(CONNECTION, 'on') and states(p) != 'unavailable' %}
{% set labels = {'accepted':'Zugesagt','uncertain':'Unsicher','declined':'Abgesagt / abwesend','pending':'Noch nicht geantwortet','not_nominated':'Nicht nominiert'} %}
Eigene Antwort: **{{ labels.get(states(p),'Unbekannt') if live else 'Nicht verfügbar' }}**

{% if live %}
{% set c = state_attr(p,'counts') or {} %}
Zusagen: **{{ c.get('accepted') if c.get('accepted') is not none else '?' }}** · Unsicher: **{{ c.get('uncertain') if c.get('uncertain') is not none else '?' }}** · Absagen: **{{ c.get('declined') if c.get('declined') is not none else '?' }}**

Offen: **{{ c.get('pending') if c.get('pending') is not none else '?' }}** · Nicht nominiert: **{{ c.get('not_nominated') if c.get('not_nominated') is not none else '?' }}**

Treffen: **{{ state_attr(p,'meeting_time') or 'nicht angegeben' }}** · Beginn: **{{ state_attr(p,'start_time') or 'nicht angegeben' }}**
{% endif %}
""".replace("PARTICIPATION", quote(participation)).replace(
            "CONNECTION", quote(connection)
        )
    return {"type": "markdown", "content": text}


def build_family_dashboard(children):
    """Accept only display names, entry IDs and entity IDs; ignore all other data."""
    cleaned = []
    for child in children:
        entities = {
            key: value
            for key, value in child.get("entities", {}).items()
            if key in ROLES
        }
        if any(not ENTITY_ID.fullmatch(value) for value in entities.values()):
            raise ValueError("Invalid entity ID")
        cleaned.append(
            {
                "entry_id": str(child["entry_id"]),
                "name": str(child["name"])[:100],
                "entities": entities,
            }
        )
    if len({child["entry_id"] for child in cleaned}) != len(cleaned):
        raise ValueError("Duplicate entry")
    views = []
    overview_sections = []
    week_sources = []
    for child in cleaned:
        entities = child["entities"]
        name = child["name"]
        path = "child-" + sha256(child["entry_id"].encode()).hexdigest()[:12]
        cards = [
            heading(name),
            next_card(entities, "next_training", "Nächstes Training"),
            next_card(entities, "next_game", "Nächstes Spiel"),
        ]
        if entities.get("connection"):
            cards.insert(
                1,
                {
                    "type": "markdown",
                    "content": "{% if state_attr("
                    + quote(entities["connection"])
                    + ", 'last_error') == 'calendar_premium_required' %}**Kalender nicht verfügbar:** SpielerPlus liefert für diese Mitgliedschaft nur einen Premium-Hinweis. Kalenderabonnement/Premium beim Anbieter prüfen. Es liegen keine echten Kalendertermine vor.{% endif %}",
                },
            )
        for role, label in [
            ("countdown", "Countdown"),
            ("events_week", "Nächste 7 Tage"),
        ]:
            if role in entities:
                cards.append({"type": "tile", "entity": entities[role], "name": label})
        overview_sections.append({"type": "grid", "cards": cards})
        details = []
        if entities.get("calendar"):
            details.append(
                {
                    "type": "calendar",
                    "entities": [entities["calendar"]],
                    "initial_view": "listWeek",
                }
            )
        diagnostics = [
            {"entity": entities[key], "name": label}
            for key, label in [
                ("connection", "Kalenderverbindung"),
                ("last_success", "Letzter Kalenderabruf"),
                ("account_connection", "Kontoverbindung"),
                ("account_last_success", "Letzter Kontoabruf"),
                ("refresh", "Aktualisieren"),
            ]
            if key in entities
        ]
        if diagnostics:
            details.append(
                {
                    "type": "entities",
                    "show_header_toggle": False,
                    "entities": diagnostics,
                }
            )
        details.append(
            {
                "type": "markdown",
                "content": "Teilnahme: erste fünf aufgelistete Termine je Mitgliedschaft. Fehlende Zähler bleiben unbekannt. Es werden keine Zu-/Absagen abgegeben.",
            }
        )
        views.append(
            {
                "title": name,
                "path": path,
                "icon": "mdi:account-child",
                "type": "sections",
                "max_columns": 2,
                "sections": [
                    {"type": "grid", "cards": cards},
                    {"type": "grid", "cards": details},
                ],
            }
        )
        if entities.get("events_week"):
            week_sources.append({"name": name, "entity": entities["events_week"]})
    week = """{% set sources = SOURCES %}
{% set ns = namespace(events=[], missing=[]) %}
{% for source in sources %}
{% if states(source.entity) not in ['unknown','unavailable'] %}
{% for event in state_attr(source.entity,'events') or [] %}
{% set ns.events = ns.events + [dict(event, child=source.name, order=as_timestamp(event.start))] %}
{% endfor %}
{% else %}
{% set ns.missing = ns.missing + [source.name] %}
{% endif %}
{% endfor %}
{% for event in ns.events | sort(attribute='order') %}
### {{ event.order | timestamp_custom('%d.%m. · %H:%M') }}

**{{ event.child }}** · {{ event.title }}

{{ event.location or 'Ort noch offen' }}

---
{% else %}
Keine aktuellen Termine in den nächsten sieben Tagen verfügbar.
{% endfor %}
{% if ns.missing %}
**Nicht alle Kalender sind aktuell:** {{ ns.missing | join(', ') }}.
{% endif %}
""".replace("SOURCES", quote(week_sources))
    overview_sections.append(
        {
            "type": "grid",
            "cards": [
                heading("Gemeinsame Sportwoche", "mdi:calendar-week"),
                {"type": "markdown", "content": week},
            ],
        }
    )
    return {
        "title": "SpielerPlus Familie",
        "views": [
            {
                "title": "Familie",
                "path": "family",
                "icon": "mdi:account-group",
                "type": "sections",
                "max_columns": 2,
                "sections": overview_sections,
            }
        ]
        + views,
    }


def write_managed_dashboard(config_dir, children, only_if_managed=False):
    path = Path(config_dir) / FILENAME
    if path.is_symlink():
        raise ValueError("Dashboard path is a symlink")
    exists = path.exists()
    if exists and not path.read_text().startswith(MARKER):
        raise ValueError("Dashboard is not managed by SpielerPlus")
    if only_if_managed and not exists:
        return False
    # Atomic write; private family names are not placed in www or repository files.
    import os, tempfile

    content = (
        MARKER
        + json.dumps(build_family_dashboard(children), indent=2, ensure_ascii=False)
        + "\n"
    )
    with tempfile.NamedTemporaryFile(
        mode="w", dir=config_dir, prefix=".spielerplus-", delete=False
    ) as file:
        temporary = Path(file.name)
        file.write(content)
    try:
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return True


def managed_dashboard_present(config_dir):
    path = Path(config_dir) / FILENAME
    return (
        path.exists() and not path.is_symlink() and path.read_text().startswith(MARKER)
    )


async def async_rebuild_dashboard(hass, only_if_managed=False):
    if only_if_managed and not await hass.async_add_executor_job(
        managed_dashboard_present, hass.config.path()
    ):
        return False
    from homeassistant.helpers import entity_registry as er
    from .const import DOMAIN

    registry = er.async_get(hass)
    children = []
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.disabled_by is not None:
            continue
        entities = {}
        for item in registry.entities.values():
            if item.platform != DOMAIN or item.config_entry_id != entry.entry_id:
                continue
            if item.unique_id == entry.entry_id:
                entities["calendar"] = item.entity_id
            elif item.unique_id.startswith(entry.entry_id + "_"):
                role = item.unique_id[len(entry.entry_id) + 1 :]
                if role in ROLES:
                    entities[role] = item.entity_id
        name = entry.data.get("child_name") or entry.title.removesuffix(" Kalender")
        children.append(
            {"entry_id": entry.entry_id, "name": name, "entities": entities}
        )
    return await hass.async_add_executor_job(
        write_managed_dashboard, hass.config.path(), children, only_if_managed
    )
