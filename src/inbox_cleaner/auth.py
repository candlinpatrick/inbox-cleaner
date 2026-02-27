"""Google OAuth flow and token management for Gmail API."""

from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build, Resource

from .models import SCOPES, TOKENS_DIR, ensure_dirs


CREDENTIALS_PATH = Path("config/credentials.json")


def _token_path(account: str) -> Path:
    """Return the token file path for an account."""
    return TOKENS_DIR / f"{account}.json"


def authenticate(account: str, credentials_path: Path | None = None) -> Credentials:
    """Run OAuth flow or refresh existing token for the given account.

    Returns valid Credentials ready for API use.
    """
    ensure_dirs()
    creds_file = credentials_path or CREDENTIALS_PATH
    token_file = _token_path(account)

    creds: Credentials | None = None

    if token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        if not creds_file.exists():
            raise FileNotFoundError(
                f"OAuth credentials not found at {creds_file}. "
                "Download credentials.json from Google Cloud Console and place it there."
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(creds_file), SCOPES)
        creds = flow.run_local_server(port=0)

    # Save token for next time
    token_file.write_text(creds.to_json())
    return creds


def get_gmail_service(account: str, credentials_path: Path | None = None) -> Resource:
    """Return an authenticated Gmail API service for the given account."""
    creds = authenticate(account, credentials_path)
    return build("gmail", "v1", credentials=creds)


def list_accounts() -> list[str]:
    """Return list of account aliases that have saved tokens."""
    ensure_dirs()
    return [p.stem for p in TOKENS_DIR.glob("*.json")]


def remove_account(account: str) -> bool:
    """Remove stored token for an account. Returns True if it existed."""
    token_file = _token_path(account)
    if token_file.exists():
        token_file.unlink()
        return True
    return False
