"""Synthetic HTML only; no account credentials, member names or health notes."""

import importlib.util
from pathlib import Path
import sys

import pytest

spec = importlib.util.spec_from_file_location(
    "spielerplus_attendance_records",
    Path(__file__).parents[1] / "custom_components/spielerplus/attendance.py",
)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def panel(event_id=101, selected=True):
    return f"""<div id="event-training-{event_id}">
    <div class="participation-widget-buttons">
      <button class="participation-button {"selected" if selected else ""}" title="Zugesagt"><div class="participation-number">12</div></button>
      <button class="participation-button" title="Unsicher"><div class="participation-number">0</div></button>
      <button class="participation-button" title="Absagen / Abwesend"><div class="participation-number">2</div></button>
    </div>
    <div class="event-time-item"><div class="event-time-label">Treffen</div><div class="event-time-value">17:45</div></div>
    <div class="event-time-item"><div class="event-time-label">Beginn</div><div class="event-time-value">18:00</div></div>
    </div>"""


def groups(own_group="99", include_unknown=False):
    result = ""
    for code, count in [("1", 12), ("2", 0), ("0", 2), ("99", 5), ("3", 0)]:
        result += f'<div class="participation-list"><h4 class="participation-list-header" data-target="#{code}-parti-collapse">Group<span class="participation-list-header-number">{count}</span></h4>'
        if code == own_group:
            result += '<div class="participation-list-user"><a href="/user/view?id=999">Fictional member</a><p>PRIVATE REASON MUST NOT BE EXPORTED</p></div>'
        result += "</div>"
    return result


def test_selected_own_status_and_true_zero():
    data, _ = module.event_summaries('<div id="events">' + panel() + "</div>")
    value = data["training:101"]
    assert value["own_status"] == "accepted"
    assert value["counts"] == {
        "accepted": 12,
        "uncertain": 0,
        "declined": 2,
        "pending": None,
        "not_nominated": None,
    }
    assert value["times"] == {"meeting_time": "17:45", "start_time": "18:00"}


def test_no_selection_is_unknown_not_pending():
    data, _ = module.event_summaries(
        '<div id="events">' + panel(selected=False) + "</div>"
    )
    assert data["training:101"]["own_status"] is None


def test_page_coverage_is_bounded():
    data, _ = module.event_summaries(
        '<div id="events">' + "".join(panel(i) for i in range(20)) + "</div>"
    )
    assert len(data) == module.MAX_EVENTS == 5


def test_private_reason_and_member_names_are_not_exported():
    counts, own = module.participation_counts(groups(), "999")
    assert counts["pending"] == 5
    assert own == "pending"
    assert "Fictional" not in repr((counts, own))
    assert "PRIVATE" not in repr((counts, own))


@pytest.mark.parametrize("code,status", module.GROUPS.items())
def test_exact_membership_controls_own_response(code, status):
    counts, own = module.participation_counts(groups(code), "999")
    assert own == status
    assert len(counts) == 5


def test_missing_own_member_not_guessed():
    counts, own = module.participation_counts(groups(), "888")
    assert own is None
    assert counts["accepted"] == 12


def test_missing_group_is_unknown_not_zero():
    counts, own = module.participation_counts(
        '<div class="participation-list"><h4 class="participation-list-header" data-target="#1-parti-collapse"><span class="participation-list-header-number">0</span></h4></div>',
        "999",
    )
    assert counts["accepted"] == 0 and counts["pending"] is None


@pytest.mark.parametrize("html", ["<p>Forbidden</p>", "<div>Server error</div>"])
def test_unrecognized_participation_does_not_become_empty_success(html):
    with pytest.raises(module.AccountError):
        module.participation_counts(html, "999")


def test_login_form_keeps_csrf_and_does_not_enable_remember():
    form = module.login_form(
        """<form action="/site/login"><input type="hidden" name="_csrf" value="FICTIONAL_TOKEN"><input type="email" name="LoginForm[email]"><input type="password" name="LoginForm[password]"><input type="checkbox" name="remember" value="1"></form>"""
    )
    assert form.fields["_csrf"] == "FICTIONAL_TOKEN"
    assert "remember" not in form.fields
    assert form.action == module.BASE + "/site/login"
    assert "FICTIONAL_TOKEN" not in repr(form)


@pytest.mark.parametrize(
    "action",
    [
        "https://evil.example/site/login",
        "http://www.spielerplus.de/site/login",
        "/site/delete",
        "//evil.example/site/login",
    ],
)
def test_credentials_never_posted_to_arbitrary_form(action):
    with pytest.raises(module.AccountError):
        module.login_form(
            f'<form action="{action}"><input type="email" name="email"><input type="password" name="password"></form>'
        )


def test_membership_selection_uses_switch_membership_not_guessed_team_id():
    html = '<div class="select-team-item"><a href="/site/switch-user?id=999"></a><div class="select-team-item-meta"><h4>Demo Team</h4><span>Demo membership</span></div></div>'
    result = module.memberships(html)
    assert set(result) == {"999"}
    assert "Demo Team" in result["999"]


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://www.spielerplus.de/training/view?id=101", "training:101"),
        ("/game/view?id=102", "game:102"),
        ("https://evil.example/game/view?id=102", None),
        ("https://www.spielerplus.de/events/ics?t=EXAMPLE&u=EXAMPLE", None),
        ("/game/view?id=not-a-number", None),
    ],
)
def test_ics_join_requires_official_event_reference(url, expected):
    assert module.event_ref(url) == expected


def test_login_page_is_not_a_successful_empty_calendar():
    with pytest.raises(module.AccountError) as error:
        module.event_summaries('<form><input type="password"></form>')
    assert error.value.code == "invalid_auth"
    assert module.event_summaries('<div id="events"></div>')[0] == {}
