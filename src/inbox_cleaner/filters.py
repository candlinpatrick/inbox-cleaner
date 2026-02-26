"""Gmail filter creation via API."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Console

from .utils import filter_exists_for_sender

if TYPE_CHECKING:
    from googleapiclient.discovery import Resource

console = Console()


def list_existing_filters(service: Resource) -> list[dict]:
    """Fetch all existing Gmail filters."""
    result = service.users().settings().filters().list(userId="me").execute()
    return result.get("filter", [])


def create_filter(service: Resource, sender_email: str, existing_filters: list[dict] | None = None) -> bool:
    """Create a Gmail filter to auto-trash mail from a sender.

    Returns True if a filter was created, False if one already existed.
    """
    from googleapiclient.errors import HttpError

    if existing_filters is None:
        existing_filters = list_existing_filters(service)

    if filter_exists_for_sender(existing_filters, sender_email):
        console.print(f"  [dim]Filter already exists for {sender_email}[/dim]")
        return False

    filter_body = {
        "criteria": {"from": sender_email},
        "action": {
            "removeLabelIds": ["INBOX"],
            "addLabelIds": ["TRASH"],
        },
    }

    try:
        service.users().settings().filters().create(
            userId="me", body=filter_body
        ).execute()
        return True
    except HttpError as e:
        console.print(f"  [red]Failed to create filter for {sender_email}: {e}[/red]")
        return False
