"""Parse and execute List-Unsubscribe headers."""

from __future__ import annotations

import base64
from email.mime.text import MIMEText
from typing import TYPE_CHECKING

import httpx
from rich.console import Console

if TYPE_CHECKING:
    from googleapiclient.discovery import Resource

console = Console()

TIMEOUT = 10  # seconds


def _send_mailto_unsubscribe(service: Resource, mailto_uri: str) -> bool:
    """Send an unsubscribe email via the Gmail API.

    mailto: URI format: mailto:unsub@example.com?subject=unsubscribe
    """
    from googleapiclient.errors import HttpError

    # Parse mailto URI
    mailto_uri = mailto_uri.removeprefix("mailto:")
    parts = mailto_uri.split("?", 1)
    to_address = parts[0]
    subject = "unsubscribe"
    body = ""

    if len(parts) > 1:
        params = dict(p.split("=", 1) for p in parts[1].split("&") if "=" in p)
        subject = params.get("subject", subject)
        body = params.get("body", body)

    message = MIMEText(body)
    message["to"] = to_address
    message["subject"] = subject

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

    try:
        service.users().messages().send(
            userId="me", body={"raw": raw}
        ).execute()
        return True
    except HttpError as e:
        console.print(f"  [red]Failed to send unsubscribe email to {to_address}: {e}[/red]")
        return False


def _hit_https_unsubscribe(url: str, post_body: str | None = None) -> bool:
    """Hit an HTTPS unsubscribe endpoint.

    If post_body is provided (from List-Unsubscribe-Post header), sends POST.
    Otherwise sends GET.
    """
    try:
        with httpx.Client(timeout=TIMEOUT, follow_redirects=True) as client:
            if post_body:
                resp = client.post(
                    url,
                    content=post_body,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
            else:
                resp = client.get(url)
            return resp.status_code < 400
    except httpx.HTTPError as e:
        console.print(f"  [red]HTTP error hitting {url}: {e}[/red]")
        return False


def attempt_unsubscribe(
    service: Resource,
    unsubscribe_links: list[str],
    unsubscribe_post: str | None = None,
) -> bool:
    """Attempt to unsubscribe using available links.

    Prefers HTTPS with One-Click (RFC 8058), then plain HTTPS, then mailto.
    Returns True if any method succeeded.
    """
    https_links = [link for link in unsubscribe_links if link.startswith(("https://", "http://"))]
    mailto_links = [link for link in unsubscribe_links if link.startswith("mailto:")]

    # 1. Try HTTPS with List-Unsubscribe-Post (RFC 8058 one-click)
    if unsubscribe_post and https_links:
        url = https_links[0]
        console.print(f"  [dim]One-click unsubscribe via POST to {url}[/dim]")
        if _hit_https_unsubscribe(url, post_body=unsubscribe_post):
            return True

    # 2. Try plain HTTPS GET
    for url in https_links:
        console.print(f"  [dim]GET unsubscribe: {url}[/dim]")
        if _hit_https_unsubscribe(url):
            return True

    # 3. Fall back to mailto
    for mailto in mailto_links:
        console.print(f"  [dim]Sending unsubscribe email: {mailto}[/dim]")
        if _send_mailto_unsubscribe(service, mailto):
            return True

    return False
