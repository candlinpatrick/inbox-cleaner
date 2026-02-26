"""Data models for inbox-cleaner."""

from datetime import datetime
from enum import Enum
from pathlib import Path

from pydantic import BaseModel


# Default paths
DATA_DIR = Path.home() / ".inbox-cleaner"
TOKENS_DIR = DATA_DIR / "tokens"
SCANS_DIR = DATA_DIR / "scans"
DECISIONS_DIR = DATA_DIR / "decisions"

# Gmail API scopes
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.settings.basic",
    "https://www.googleapis.com/auth/gmail.send",
]


class Decision(str, Enum):
    KEEP = "keep"
    FILTER_DELETE = "filter_delete"
    UNSUBSCRIBE = "unsubscribe"
    SKIP = "skip"


class Sender(BaseModel):
    email: str
    display_name: str
    message_count: int
    frequency_estimate: str  # "daily", "2-3/week", "weekly", "monthly"
    category: str | None = None  # PROMOTIONS, UPDATES, SOCIAL, etc.
    has_unsubscribe_header: bool
    unsubscribe_links: list[str] = []
    unsubscribe_post: str | None = None  # List-Unsubscribe-Post value
    sample_subjects: list[str] = []
    message_ids: list[str] = []  # Gmail message IDs for bulk operations
    first_seen: datetime
    last_seen: datetime


class SenderDecision(BaseModel):
    sender: Sender
    decision: Decision
    decided_at: datetime


class ScanResult(BaseModel):
    account: str
    scanned_at: datetime
    days_scanned: int
    total_messages: int
    senders: list[Sender]


class ApplyResult(BaseModel):
    filters_created: int = 0
    messages_deleted: int = 0
    unsubscribe_attempted: int = 0
    unsubscribe_succeeded: int = 0
    errors: list[str] = []


def ensure_dirs() -> None:
    """Create data directories if they don't exist."""
    for d in (TOKENS_DIR, SCANS_DIR, DECISIONS_DIR):
        d.mkdir(parents=True, exist_ok=True)
