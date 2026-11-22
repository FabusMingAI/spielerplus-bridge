"""Subscription validation and stable identities without Home Assistant imports."""

from hashlib import sha256
from urllib.parse import urlparse


def normalize_subscription(value):
    value = value.strip()
    if value.startswith("webcal://"):
        value = "https://" + value[len("webcal://") :]
    parsed = urlparse(value)
    if (
        parsed.scheme != "https"
        or parsed.netloc != "www.spielerplus.de"
        or parsed.path != "/events/ics"
        or not parsed.query
        or parsed.username
        or parsed.password
        or parsed.fragment
    ):
        raise ValueError("Invalid subscription")
    return value


def subscription_identity(url, membership_id=None):
    # Existing calendar-only IDs stay unchanged for backwards compatibility.
    if membership_id is None:
        return url
    return f"membership:{membership_id}:{sha256(url.encode()).hexdigest()}"


def subscription_conflict(entries, url, membership_id=None):
    for data, options in entries:
        if data.get("url") != url:
            continue
        if membership_id is None or str(options.get("membership_id", "")) == str(
            membership_id
        ):
            return True
    return False


def calendar_subscription(html):
    """Use one unambiguous official subscription or require manual input."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    values = set()
    for node in soup.find_all(["a", "input"]):
        value = node.get("href") or node.get("value", "")
        try:
            values.add(normalize_subscription(value))
        except ValueError:
            pass
    return next(iter(values)) if len(values) == 1 else None
