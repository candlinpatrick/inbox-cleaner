# CLAUDE.md — Project context for Claude Code

## What is this?

inbox-cleaner is a Python CLI tool that connects to Gmail via OAuth, scans for newsletter/promotional senders, and lets you interactively triage them — creating filters, bulk-deleting old messages, and optionally hitting unsubscribe endpoints. Designed for multiple Gmail accounts.

## Project structure

```
src/inbox_cleaner/
├── cli.py         # Typer CLI entry point (auth, scan, triage, apply, status)
├── auth.py        # Google OAuth flow + token management
├── scanner.py     # Scan inbox for newsletter/promo senders via Gmail API
├── triage.py      # Interactive sender triage UI (Rich panels)
├── filters.py     # Gmail filter creation via API
├── cleanup.py     # Bulk delete/archive existing messages
├── unsubscribe.py # Parse & hit List-Unsubscribe headers
├── models.py      # Pydantic data models (Sender, Decision, ScanResult, etc.)
└── utils.py       # Pure utility functions (parsing, frequency estimation)
```

## Key commands

```bash
pip install -e ".[dev]"    # Install with dev deps
pytest                     # Run tests (35 tests, pure-logic only)
inbox-cleaner --help       # Show CLI help
```

## Architecture notes

- **Google API imports are deferred** — modules use `TYPE_CHECKING` guards and lazy imports so that pure-logic tests run without the Google API client loaded.
- **utils.py** contains all pure functions (parsing, frequency estimation, filter matching) extracted for testability.
- All user data stored in `~/.inbox-cleaner/` (tokens, scans, decisions).
- `config/credentials.json` is gitignored — users provide their own OAuth credentials.
- Rate limiting uses exponential backoff on HTTP 429s.

## Gmail API scopes used

- `gmail.readonly` — scan messages
- `gmail.modify` — delete/archive messages
- `gmail.settings.basic` — create filters
- `gmail.send` — send unsubscribe emails
