"""inbox-cleaner CLI — scan, triage, and clean up Gmail clutter."""

from datetime import datetime, timezone
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .models import Decision, ApplyResult, ensure_dirs

app = typer.Typer(
    name="inbox-cleaner",
    help="Kill newsletter and promo email clutter across multiple Gmail accounts.",
    no_args_is_help=True,
)
console = Console()


@app.command()
def auth(
    account: str = typer.Option("default", help="Account alias for multi-account support"),
    credentials: Path = typer.Option(
        Path("config/credentials.json"),
        help="Path to Google OAuth credentials JSON",
    ),
):
    """Authenticate a Gmail account via OAuth."""
    from .auth import authenticate

    console.print(f"[bold]Authenticating account: {account}[/bold]")
    try:
        authenticate(account, credentials)
        console.print(f"[green]Successfully authenticated '{account}'.[/green]")
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Authentication failed: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def scan(
    account: str = typer.Option("default", help="Account alias"),
    days: int = typer.Option(30, help="Number of days to scan"),
):
    """Scan inbox for newsletter/promotional senders."""
    from .auth import get_gmail_service
    from .scanner import scan_inbox

    console.print(f"[bold]Scanning '{account}' — last {days} days[/bold]")

    try:
        service = get_gmail_service(account)
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    result = scan_inbox(service, account, days)
    console.print(
        f"\n[green]Done![/green] Found [bold]{len(result.senders)}[/bold] unique senders "
        f"across [bold]{result.total_messages}[/bold] messages."
    )

    # Show top senders preview
    if result.senders:
        table = Table(title="Top senders", show_lines=False)
        table.add_column("Sender", style="cyan")
        table.add_column("Count", justify="right")
        table.add_column("Freq")
        table.add_column("Category")
        table.add_column("Unsub?")

        for s in result.senders[:15]:
            name = s.display_name or s.email
            if len(name) > 40:
                name = name[:37] + "..."
            unsub = "yes" if s.has_unsubscribe_header else ""
            table.add_row(name, str(s.message_count), s.frequency_estimate, s.category or "", unsub)

        console.print(table)


@app.command()
def triage(
    account: str = typer.Option("default", help="Account alias"),
    auto_recommend: bool = typer.Option(False, "--auto-recommend", help="Pre-fill recommendations"),
):
    """Interactively triage senders: keep, filter+delete, or unsubscribe."""
    from .scanner import load_latest_scan
    from .triage import run_triage

    console.print(f"[bold]Triaging '{account}'[/bold]")

    scan_result = load_latest_scan(account)
    if not scan_result:
        console.print(
            f"[red]No scan results found for '{account}'. Run 'inbox-cleaner scan' first.[/red]"
        )
        raise typer.Exit(1)

    console.print(
        f"  Using scan from {scan_result.scanned_at.strftime('%Y-%m-%d %H:%M')} "
        f"({len(scan_result.senders)} senders)\n"
    )

    run_triage(scan_result, account, auto_recommend_flag=auto_recommend)


@app.command()
def apply(
    account: str = typer.Option("default", help="Account alias"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview changes without applying"),
):
    """Apply triage decisions: create filters, delete messages, unsubscribe."""
    from .auth import get_gmail_service
    from .triage import load_decisions
    from .filters import create_filter, list_existing_filters
    from .cleanup import delete_messages_from_sender
    from .unsubscribe import attempt_unsubscribe

    mode = "[yellow]DRY RUN[/yellow]" if dry_run else "[red]LIVE[/red]"
    console.print(f"[bold]Applying decisions for '{account}' ({mode})[/bold]\n")

    decisions = load_decisions(account)
    if not decisions:
        console.print(f"[red]No decisions found for '{account}'. Run 'inbox-cleaner triage' first.[/red]")
        raise typer.Exit(1)

    actionable = [d for d in decisions if d.decision in (Decision.FILTER_DELETE, Decision.UNSUBSCRIBE)]
    if not actionable:
        console.print("[green]No filter/delete/unsubscribe actions to apply.[/green]")
        return

    console.print(f"  {len(actionable)} senders to process\n")

    result = ApplyResult()

    if not dry_run:
        try:
            service = get_gmail_service(account)
        except FileNotFoundError as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(1)

        existing_filters = list_existing_filters(service)

    for sd in actionable:
        sender = sd.sender
        label = "Filter+Delete" if sd.decision == Decision.FILTER_DELETE else "Unsubscribe"
        console.print(f"[bold]{label}:[/bold] {sender.display_name or sender.email} <{sender.email}>")

        if dry_run:
            console.print(f"  Would create filter for {sender.email}")
            console.print(f"  Would delete messages from {sender.email}")
            if sd.decision == Decision.UNSUBSCRIBE and sender.unsubscribe_links:
                console.print(f"  Would attempt unsubscribe via {sender.unsubscribe_links[0]}")
            console.print()
            continue

        # Create filter
        if create_filter(service, sender.email, existing_filters):
            result.filters_created += 1
            console.print(f"  [green]Filter created[/green]")

        # Delete existing messages
        deleted = delete_messages_from_sender(service, sender.email)
        result.messages_deleted += deleted

        # Unsubscribe
        if sd.decision == Decision.UNSUBSCRIBE and sender.unsubscribe_links:
            result.unsubscribe_attempted += 1
            if attempt_unsubscribe(service, sender.unsubscribe_links, sender.unsubscribe_post):
                result.unsubscribe_succeeded += 1
                console.print(f"  [green]Unsubscribed[/green]")
            else:
                console.print(f"  [yellow]Unsubscribe attempt failed[/yellow]")
                result.errors.append(f"Unsubscribe failed for {sender.email}")

        console.print()

    # Summary
    console.print("[bold]Summary:[/bold]")
    if dry_run:
        console.print(f"  (Dry run — no changes made)")
    else:
        console.print(f"  Filters created: {result.filters_created}")
        console.print(f"  Messages deleted: {result.messages_deleted}")
        if result.unsubscribe_attempted:
            console.print(
                f"  Unsubscribe: {result.unsubscribe_succeeded}/{result.unsubscribe_attempted} succeeded"
            )
        if result.errors:
            console.print(f"  [yellow]Errors: {len(result.errors)}[/yellow]")
            for err in result.errors:
                console.print(f"    - {err}")


@app.command()
def status(
    account: str = typer.Option(None, help="Show status for a specific account (default: all)"),
):
    """Show overview of accounts, scans, and pending decisions."""
    from .auth import list_accounts
    from .scanner import load_latest_scan
    from .triage import load_decisions
    from .models import SCANS_DIR

    console.print("[bold]inbox-cleaner status[/bold]\n")

    accounts = [account] if account else list_accounts()

    if not accounts:
        console.print("[yellow]No accounts configured. Run 'inbox-cleaner auth' to add one.[/yellow]")
        return

    for acct in accounts:
        console.print(f"[bold cyan]Account: {acct}[/bold cyan]")

        # Latest scan info
        scan_result = load_latest_scan(acct)
        if scan_result:
            console.print(
                f"  Last scan: {scan_result.scanned_at.strftime('%Y-%m-%d %H:%M')} "
                f"({scan_result.days_scanned} days, {len(scan_result.senders)} senders)"
            )
        else:
            console.print("  Last scan: [dim]none[/dim]")

        # Decision stats
        decisions = load_decisions(acct)
        if decisions:
            counts: dict[str, int] = {}
            for d in decisions:
                counts[d.decision.value] = counts.get(d.decision.value, 0) + 1
            parts = [f"{v} {k}" for k, v in counts.items()]
            console.print(f"  Decisions: {', '.join(parts)}")
            pending = sum(1 for d in decisions if d.decision == Decision.SKIP)
            if pending:
                console.print(f"  [yellow]Pending (skipped): {pending}[/yellow]")
        else:
            console.print("  Decisions: [dim]none[/dim]")

        console.print()


if __name__ == "__main__":
    app()
