"""Pure utility functions — no external API dependencies."""

import re


def parse_from_header(from_header: str) -> tuple[str, str]:
    """Extract display name and email from a From header value.

    Examples:
        "Foo Bar <foo@bar.com>" -> ("Foo Bar", "foo@bar.com")
        "foo@bar.com" -> ("", "foo@bar.com")
    """
    match = re.match(r"^(.*?)\s*<([^>]+)>$", from_header)
    if match:
        display_name = match.group(1).strip().strip('"')
        email = match.group(2).strip().lower()
        return display_name, email
    # Bare email
    email = from_header.strip().lower()
    return "", email


def parse_unsubscribe_header(header_value: str) -> list[str]:
    """Parse List-Unsubscribe header into a list of URIs.

    Header format: <https://example.com/unsub>, <mailto:unsub@example.com>
    """
    links = []
    for part in header_value.split(","):
        part = part.strip()
        match = re.match(r"<(.+)>", part)
        if match:
            links.append(match.group(1))
    return links


def estimate_frequency(count: int, days: int) -> str:
    """Estimate sending frequency from message count over a time period."""
    if days <= 0:
        return "unknown"
    per_day = count / days
    if per_day >= 1.5:
        return "daily+"
    if per_day >= 0.8:
        return "daily"
    if per_day >= 0.35:
        return "2-3/week"
    if per_day >= 0.12:
        return "weekly"
    if per_day >= 0.05:
        return "biweekly"
    return "monthly"


# Gmail category label ID → display name
CATEGORY_LABELS = {
    "CATEGORY_PROMOTIONS": "PROMOTIONS",
    "CATEGORY_UPDATES": "UPDATES",
    "CATEGORY_SOCIAL": "SOCIAL",
    "CATEGORY_FORUMS": "FORUMS",
    "CATEGORY_PERSONAL": "PERSONAL",
}


def get_category(label_ids: list[str]) -> str | None:
    """Extract Gmail category from label IDs."""
    for lid in label_ids:
        if lid in CATEGORY_LABELS:
            return CATEGORY_LABELS[lid]
    return None


def filter_exists_for_sender(existing_filters: list[dict], sender_email: str) -> bool:
    """Check if a Gmail filter already exists for a given sender."""
    for f in existing_filters:
        criteria = f.get("criteria", {})
        if criteria.get("from", "").lower() == sender_email.lower():
            return True
    return False
