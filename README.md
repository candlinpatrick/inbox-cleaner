# inbox-cleaner

Kill newsletter and promotional email clutter across multiple Gmail accounts. Scans your inbox, lets you interactively decide what stays and what goes, then creates filters and bulk-deletes in one shot.

## Setup

### 1. Google Cloud credentials

You need OAuth credentials to access Gmail's API:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or use existing)
3. Enable the **Gmail API** (`APIs & Services → Enable APIs`)
4. Go to `APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID`
5. Choose **Desktop app** as the application type
6. Download the JSON file and save it as `config/credentials.json`

> **Note:** `config/credentials.json` is gitignored — never commit OAuth credentials.

### 2. Install

```bash
cd inbox-cleaner
pip install -e .
```

For development:
```bash
pip install -e ".[dev]"
```

### 3. Authenticate

```bash
# Add your personal Gmail
inbox-cleaner auth --account personal

# Add a work account
inbox-cleaner auth --account work
```

This opens a browser for Google OAuth consent. Tokens are stored in `~/.inbox-cleaner/tokens/`.

## Usage

```bash
# Scan for newsletter/promo senders (last 30 days)
inbox-cleaner scan --account personal
inbox-cleaner scan --account work --days 60

# Interactively triage each sender
inbox-cleaner triage --account personal

# Use auto-recommendations based on category/frequency
inbox-cleaner triage --account personal --auto-recommend

# Preview what would happen
inbox-cleaner apply --account personal --dry-run

# Apply decisions (create filters, delete messages, unsubscribe)
inbox-cleaner apply --account personal

# Check status across all accounts
inbox-cleaner status
```

## How it works

1. **Scan** queries Gmail for messages with `List-Unsubscribe` headers or "unsubscribe" in the body, groups by sender, and caches results locally.

2. **Triage** presents each sender with volume, frequency, category, and sample subjects. You choose:
   - **Keep** — no action
   - **Filter+Delete** — create Gmail filter to auto-trash + bulk delete existing
   - **Unsubscribe** — all of the above + hit unsubscribe endpoint
   - **Skip** — come back later

3. **Apply** creates Gmail filters to auto-trash future emails, bulk-deletes existing messages, and optionally hits unsubscribe endpoints (via `List-Unsubscribe` headers / RFC 8058 one-click).

## Data storage

All data is local:
```
~/.inbox-cleaner/
├── tokens/          # OAuth refresh tokens (per account)
├── scans/           # Cached scan results
└── decisions/       # Your triage decisions
```

## Running tests

```bash
pytest
```
