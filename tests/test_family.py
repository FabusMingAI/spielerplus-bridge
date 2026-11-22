"""Synthetic family entries; same-feed siblings and dashboard separation."""

import importlib.util
import json
from pathlib import Path
import sys

import pytest

BASE = Path(__file__).parents[1] / "custom_components/spielerplus"


def load(name):
    spec = importlib.util.spec_from_file_location(
        "family_test_" + name, BASE / (name + ".py")
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


helpers = load("config_helpers")
dashboard = load("dashboard")
URL = "https://www.spielerplus.de/events/ics?t=EXAMPLE&u=EXAMPLE"


def child(name, entry_id, prefix):
    return {
        "entry_id": entry_id,
        "name": name,
        "account_password": "NEVER_EXPORT_THIS",
        "entities": {
            key: f"{domain}.{prefix}_{key}"
            for key, domain in [
                ("calendar", "calendar"),
                ("next_training", "sensor"),
                ("next_game", "sensor"),
                ("events_week", "sensor"),
                ("countdown", "sensor"),
                ("connection", "binary_sensor"),
                ("training_participation", "sensor"),
                ("game_participation", "sensor"),
                ("account_connection", "binary_sensor"),
            ]
        },
    }


def test_same_feed_allows_distinct_children_but_not_duplicate_membership():
    entries = [({"url": URL}, {"membership_id": "101"})]
    assert not helpers.subscription_conflict(entries, URL, "202")
    assert helpers.subscription_conflict(entries, URL, "101")
    assert helpers.subscription_conflict(entries, URL)
    assert helpers.subscription_identity(URL, "101") != helpers.subscription_identity(
        URL, "202"
    )
    assert helpers.subscription_identity(URL) == URL
    assert URL not in helpers.subscription_identity(URL, "101")


def test_subscription_discovery_requires_one_official_url():
    html = f'<a href="{URL}">Calendar</a><input value="{URL}">'
    assert helpers.calendar_subscription(html) == URL
    assert (
        helpers.calendar_subscription('<a href="https://evil.example/feed">Fake</a>')
        is None
    )
    assert (
        helpers.calendar_subscription(html + f'<a href="{URL}&other=1">Second</a>')
        is None
    )


def test_normalize_webcal_keeps_private_endpoint_rules():
    assert helpers.normalize_subscription(URL.replace("https:", "webcal:")) == URL
    for invalid in [
        "http://www.spielerplus.de/events/ics?t=EXAMPLE",
        "https://www.spielerplus.de.evil.example/events/ics?t=EXAMPLE",
        URL + "#fragment",
    ]:
        with pytest.raises(ValueError):
            helpers.normalize_subscription(invalid)


def test_family_has_overview_and_separate_stable_child_views():
    a, b = child("Lea", "entry-one", "lea"), child("Ben", "entry-two", "ben")
    result = dashboard.build_family_dashboard([a, b])
    assert [view["title"] for view in result["views"]] == ["Familie", "Lea", "Ben"]
    assert result["views"][1]["path"] != result["views"][2]["path"]
    assert "sensor.lea_next_training" in json.dumps(result["views"][1])
    assert "sensor.ben_next_training" not in json.dumps(result["views"][1])
    assert "sensor.ben_next_training" in json.dumps(result["views"][2])
    assert "NEVER_EXPORT_THIS" not in json.dumps(result)
    renamed = dashboard.build_family_dashboard([{**a, "name": "New name"}, b])
    assert renamed["views"][1]["path"] == result["views"][1]["path"]


def test_missing_child_entities_render_setup_message_not_guess_ids():
    result = dashboard.build_family_dashboard(
        [{"entry_id": "new", "name": "New child", "entities": {}}]
    )
    assert "noch eingerichtet" in json.dumps(result)
    assert "sensor.spielerplus" not in json.dumps(result)


def test_missing_counts_stay_unknown_and_unavailable_source_is_guarded():
    result = dashboard.build_family_dashboard([child("Lea", "one", "lea")])
    serialized = json.dumps(result)
    assert "not in" in serialized and "unavailable" in serialized
    assert "is not none" in serialized
    assert "as_timestamp(event.start)" in serialized


def test_non_entity_template_values_are_rejected():
    item = child("Lea", "one", "lea")
    item["entities"]["next_training"] = "sensor.x' }}"
    with pytest.raises(ValueError):
        dashboard.build_family_dashboard([item])


def test_managed_file_creation_and_foreign_file_preservation(tmp_path):
    children = [child("Lea", "one", "lea")]
    assert not dashboard.write_managed_dashboard(
        tmp_path, children, only_if_managed=True
    )
    assert dashboard.write_managed_dashboard(tmp_path, children)
    path = tmp_path / dashboard.FILENAME
    assert path.read_text().startswith(dashboard.MARKER)
    assert "Lea" in json.loads(path.read_text().split("\n", 1)[1])["views"][1]["title"]
    path.write_text("my existing dashboard")
    with pytest.raises(ValueError):
        dashboard.write_managed_dashboard(tmp_path, children)
    assert path.read_text() == "my existing dashboard"


def test_symlink_and_duplicate_entry_are_rejected(tmp_path):
    target = tmp_path / "untouched"
    target.write_text("private")
    (tmp_path / dashboard.FILENAME).symlink_to(target)
    with pytest.raises(ValueError):
        dashboard.write_managed_dashboard(tmp_path, [])
    assert target.read_text() == "private"
    item = child("Lea", "one", "lea")
    with pytest.raises(ValueError):
        dashboard.build_family_dashboard([item, item])


def test_premium_placeholder_is_not_a_real_calendar():
    from types import SimpleNamespace

    calendar_notice = load("events").calendar_notice

    assert (
        calendar_notice([SimpleNamespace(title="Premium-Feature")])
        == "calendar_premium_required"
    )
    assert calendar_notice([]) is None
    assert calendar_notice([SimpleNamespace(title="Training")]) is None
    assert (
        calendar_notice(
            [
                SimpleNamespace(title="Premium-Feature"),
                SimpleNamespace(title="Training"),
            ]
        )
        is None
    )
