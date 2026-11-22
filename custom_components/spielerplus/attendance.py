"""Read-only account data: aggregate counts and own status, never member names."""

from dataclasses import dataclass, field
import re
from urllib.parse import parse_qs, urlparse, urljoin

from bs4 import BeautifulSoup

BASE = "https://www.spielerplus.de"
MAX_HTML_BYTES = 3_000_000
MAX_EVENTS = 5
STATUSES = ("accepted", "uncertain", "declined", "pending", "not_nominated")
GROUPS = {
    "1": "accepted",
    "2": "uncertain",
    "0": "declined",
    "99": "pending",
    "3": "not_nominated",
}
LABELS = {
    "Zugesagt": "accepted",
    "Unsicher": "uncertain",
    "Absagen / Abwesend": "declined",
}


class AccountError(Exception):
    """Only static, translated codes may escape the account boundary."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def official_url(value):
    value = urljoin(BASE, value)
    parsed = urlparse(value)
    if (
        parsed.scheme != "https"
        or parsed.netloc != "www.spielerplus.de"
        or parsed.username
        or parsed.password
        or parsed.fragment
    ):
        raise AccountError("unexpected_response")
    return value


def event_ref(url):
    parsed = urlparse(urljoin(BASE, url))
    match = re.fullmatch(
        r"/(training|game|event|tournament|activity)/view", parsed.path
    )
    event_id = parse_qs(parsed.query).get("id", [""])[0]
    if (
        parsed.netloc != "www.spielerplus.de"
        or parsed.scheme != "https"
        or not match
        or not event_id.isdigit()
    ):
        return None
    return f"{match[1]}:{event_id}"


@dataclass
class LoginForm:
    action: str
    email_field: str
    password_field: str
    fields: dict = field(repr=False)


def login_form(html):
    soup = BeautifulSoup(html, "html.parser")
    password = soup.find("input", type="password")
    form = password.find_parent("form") if password else None
    if form is None:
        raise AccountError("unsupported_login")
    email = next(
        (
            item
            for item in form.find_all("input")
            if item.get("type") == "email"
            or re.search(r"email|username", item.get("name", ""), re.I)
        ),
        None,
    )
    if email is None or not email.get("name") or not password.get("name"):
        raise AccountError("unsupported_login")
    action = official_url(form.get("action") or "/site/login")
    if urlparse(action).path != "/site/login":
        raise AccountError("unsupported_login")
    fields = {}
    for item in form.find_all("input"):
        kind, name = item.get("type", "text").lower(), item.get("name")
        if not name or kind in {"submit", "button", "file"}:
            continue
        if kind in {"checkbox", "radio"} and not item.has_attr("checked"):
            continue
        fields[name] = item.get("value", "")
    return LoginForm(action, email["name"], password["name"], fields)


def memberships(html):
    soup = BeautifulSoup(html, "html.parser")
    result = {}
    for item in soup.select(".select-team-item"):
        link = item.find("a", href=re.compile(r"^/site/switch-user\?id=\d+(?:&|$)"))
        name = item.select_one(".select-team-item-meta h4")
        if link and name:
            member_id = parse_qs(urlparse(link["href"]).query)["id"][0]
            meta = item.select_one(".select-team-item-meta")
            result[member_id] = (
                meta.get_text(" · ", strip=True)[:200]
                if meta
                else name.get_text(" ", strip=True)
            )
    if not result:
        if soup.find("input", type="password"):
            raise AccountError("invalid_auth")
        raise AccountError("no_memberships")
    return result


def count_value(node):
    text = node.get_text(strip=True) if node else ""
    return int(text) if text.isdigit() else None


def event_summaries(html):
    soup = BeautifulSoup(html, "html.parser")
    if soup.find("input", type="password"):
        raise AccountError("invalid_auth")
    container = soup.select_one("#events")
    if container is None:
        raise AccountError("unexpected_response")
    result = {}
    for panel in container.select('[id^="event-"]'):
        match = re.fullmatch(
            r"event-(training|game|event|tournament|activity)-(\d+)",
            panel.get("id", ""),
        )
        if not match or len(result) >= MAX_EVENTS:
            continue
        counts = {key: None for key in STATUSES}
        own_status = None
        for button in panel.select(
            ".participation-widget-buttons .participation-button"
        ):
            status = LABELS.get(button.get("title"))
            if status:
                counts[status] = count_value(button.select_one(".participation-number"))
                if "selected" in button.get("class", []):
                    own_status = status
        times = {}
        for item in panel.select(".event-time-item"):
            label, value = (
                item.select_one(".event-time-label"),
                item.select_one(".event-time-value"),
            )
            if label and value:
                key = {
                    "Treffen": "meeting_time",
                    "Beginn": "start_time",
                    "Ende": "end_time",
                }.get(label.get_text(strip=True))
                text = value.get_text(strip=True)
                if key and re.fullmatch(r"\d{1,2}:\d{2}", text):
                    times[key] = text
        result[f"{match[1]}:{match[2]}"] = {
            "event_type": match[1],
            "event_id": match[2],
            "own_status": own_status,
            "counts": counts,
            "times": times,
            "detail_error": None,
        }
    csrf = soup.find("meta", attrs={"name": "csrf-token"})
    param = soup.find("meta", attrs={"name": "csrf-param"})
    return result, (
        param.get("content", "_csrf") if param else "_csrf",
        csrf.get("content", "") if csrf else "",
    )


def participation_counts(html, member_id):
    """Only inspect group headers and the matching own membership link."""
    soup = BeautifulSoup(html, "html.parser")
    counts = {key: None for key in STATUSES}
    own_status = None
    found = False
    for block in soup.select(".participation-list"):
        header = block.select_one(".participation-list-header")
        if header is None:
            continue
        target = header.get("data-target", "")
        match = re.fullmatch(r"#(99|0|1|2|3)-parti-collapse", target)
        if not match:
            continue
        status = GROUPS[match[1]]
        counts[status] = count_value(
            header.select_one(".participation-list-header-number")
        )
        found = True
        if block.find("a", href=f"/user/view?id={member_id}"):
            own_status = status
    if not found:
        raise AccountError("unexpected_response")
    return counts, own_status
