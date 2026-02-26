"""Bulk delete/archive existing messages from senders."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn

if TYPE_CHECKING:
    from googleapiclient.discovery import Resource

console = Console()

# Gmail batchDelete accepts max 1000 IDs per call
BATCH_SIZE = 1000


def _api_call_with_backoff(fn, max_retries: int = 5):
    """Execute API call with exponential backoff on 429s."""
    from googleapiclient.errors import HttpError

    for attempt in range(max_retries + 1):
        try:
            return fn()
        except HttpError as e:
            if e.resp.status == 429 and attempt < max_retries:
                wait = 2 ** attempt
                time.sleep(wait)
                continue
            raise


def find_messages_from_sender(service: Resource, sender_email: str) -> list[str]:
    """Find all message IDs from a given sender."""
    message_ids: list[str] = []
    page_token = None
    query = f"from:{sender_email}"

    while True:
        result = _api_call_with_backoff(
            lambda: service.users().messages().list(
                userId="me",
                q=query,
                pageToken=page_token,
                maxResults=500,
            ).execute()
        )
        for msg in result.get("messages", []):
            message_ids.append(msg["id"])
        page_token = result.get("nextPageToken")
        if not page_token:
            break

    return message_ids


def bulk_delete_messages(service: Resource, message_ids: list[str], sender_email: str) -> int:
    """Batch delete messages by ID. Returns number of messages deleted."""
    from googleapiclient.errors import HttpError

    if not message_ids:
        return 0

    deleted = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(
            f"Deleting {len(message_ids)} messages from {sender_email}...",
            total=len(message_ids),
        )

        for i in range(0, len(message_ids), BATCH_SIZE):
            batch = message_ids[i : i + BATCH_SIZE]
            try:
                _api_call_with_backoff(
                    lambda b=batch: service.users().messages().batchDelete(
                        userId="me",
                        body={"ids": b},
                    ).execute()
                )
                deleted += len(batch)
                progress.update(task, advance=len(batch))
            except HttpError as e:
                console.print(f"  [red]Error deleting batch: {e}[/red]")

    return deleted


def delete_messages_from_sender(service: Resource, sender_email: str) -> int:
    """Find and delete all messages from a sender. Returns count deleted."""
    message_ids = find_messages_from_sender(service, sender_email)
    if not message_ids:
        console.print(f"  [dim]No messages found from {sender_email}[/dim]")
        return 0
    return bulk_delete_messages(service, message_ids, sender_email)
