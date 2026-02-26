"""Scan Gmail inbox for newsletter/promotional senders."""

from __future__ import annotations

import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn

from .models import Sender, ScanResult, SCANS_DIR, ensure_dirs
from .utils import parse_from_header, parse_unsubscribe_header, estimate_frequency, get_category

if TYPE_CHECKING:
    from googleapiclient.discovery import Resource

console = Console()


def _api_call_with_backoff(fn, max_retries: int = 5):
    """Execute a Gmail API call with exponential backoff on rate limit errors."""
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


def scan_inbox(service: Resource, account: str, days: int = 30) -> ScanResult:
    """Scan Gmail inbox for newsletter/promotional senders.

    Queries for messages containing unsubscribe indicators, groups by sender,
    and returns structured results.
    """
    ensure_dirs()

    # Query for messages with unsubscribe content
    query = f"unsubscribe newer_than:{days}d"

    console.print(f"  Searching for messages matching: [cyan]{query}[/cyan]")

    # Collect all message IDs
    message_stubs: list[dict] = []
    page_token = None

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Listing messages...", total=None)
        while True:
            result = _api_call_with_backoff(
                lambda: service.users().messages().list(
                    userId="me",
                    q=query,
                    pageToken=page_token,
                    maxResults=500,
                ).execute()
            )
            batch = result.get("messages", [])
            message_stubs.extend(batch)
            progress.update(task, description=f"Found {len(message_stubs)} messages...")
            page_token = result.get("nextPageToken")
            if not page_token:
                break

    if not message_stubs:
        console.print("  No messages found matching the query.")
        return ScanResult(
            account=account,
            scanned_at=datetime.now(timezone.utc),
            days_scanned=days,
            total_messages=0,
            senders=[],
        )

    console.print(f"  Found [bold]{len(message_stubs)}[/bold] messages. Fetching headers...")

    # Fetch metadata for each message
    sender_data: dict[str, dict] = defaultdict(lambda: {
        "display_name": "",
        "email": "",
        "count": 0,
        "subjects": [],
        "message_ids": [],
        "has_unsubscribe": False,
        "unsubscribe_links": [],
        "unsubscribe_post": None,
        "categories": [],
        "dates": [],
    })

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Fetching message details...", total=len(message_stubs))
        for stub in message_stubs:
            msg = _api_call_with_backoff(
                lambda mid=stub["id"]: service.users().messages().get(
                    userId="me",
                    id=mid,
                    format="metadata",
                    metadataHeaders=[
                        "From", "Subject", "List-Unsubscribe", "List-Unsubscribe-Post",
                    ],
                ).execute()
            )

            headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
            from_header = headers.get("From", "")
            subject = headers.get("Subject", "(no subject)")
            unsub_header = headers.get("List-Unsubscribe", "")
            unsub_post = headers.get("List-Unsubscribe-Post", "")
            label_ids = msg.get("labelIds", [])

            display_name, email = parse_from_header(from_header)
            if not email:
                progress.advance(task)
                continue

            data = sender_data[email]
            data["email"] = email
            if display_name and not data["display_name"]:
                data["display_name"] = display_name
            data["count"] += 1
            data["message_ids"].append(msg["id"])
            if subject and len(data["subjects"]) < 3:
                data["subjects"].append(subject)
            if unsub_header:
                data["has_unsubscribe"] = True
                links = parse_unsubscribe_header(unsub_header)
                if links and not data["unsubscribe_links"]:
                    data["unsubscribe_links"] = links
            if unsub_post and not data["unsubscribe_post"]:
                data["unsubscribe_post"] = unsub_post

            category = get_category(label_ids)
            if category and category not in data["categories"]:
                data["categories"].append(category)

            # Track dates for first/last seen
            internal_date = int(msg.get("internalDate", 0))
            if internal_date:
                data["dates"].append(internal_date)

            progress.advance(task)

    # Build Sender objects
    senders: list[Sender] = []
    for email, data in sender_data.items():
        dates = data["dates"]
        if not dates:
            now = datetime.now(timezone.utc)
            first_seen = last_seen = now
        else:
            first_seen = datetime.fromtimestamp(min(dates) / 1000, tz=timezone.utc)
            last_seen = datetime.fromtimestamp(max(dates) / 1000, tz=timezone.utc)

        primary_category = data["categories"][0] if data["categories"] else None

        senders.append(Sender(
            email=email,
            display_name=data["display_name"],
            message_count=data["count"],
            frequency_estimate=estimate_frequency(data["count"], days),
            category=primary_category,
            has_unsubscribe_header=data["has_unsubscribe"],
            unsubscribe_links=data["unsubscribe_links"],
            unsubscribe_post=data["unsubscribe_post"],
            sample_subjects=data["subjects"],
            message_ids=data["message_ids"],
            first_seen=first_seen,
            last_seen=last_seen,
        ))

    # Sort by message count descending
    senders.sort(key=lambda s: s.message_count, reverse=True)

    result = ScanResult(
        account=account,
        scanned_at=datetime.now(timezone.utc),
        days_scanned=days,
        total_messages=len(message_stubs),
        senders=senders,
    )

    # Cache results
    scan_file = SCANS_DIR / f"{account}_{result.scanned_at.strftime('%Y%m%d_%H%M%S')}.json"
    scan_file.write_text(result.model_dump_json(indent=2))
    console.print(f"  Scan cached to [dim]{scan_file}[/dim]")

    return result


def load_latest_scan(account: str) -> ScanResult | None:
    """Load the most recent scan result for an account."""
    ensure_dirs()
    scan_files = sorted(SCANS_DIR.glob(f"{account}_*.json"), reverse=True)
    if not scan_files:
        return None
    return ScanResult.model_validate_json(scan_files[0].read_text())
