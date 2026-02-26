"""Interactive sender triage UI using Rich."""

import json
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .models import (
    Decision,
    Sender,
    SenderDecision,
    ScanResult,
    DECISIONS_DIR,
    ensure_dirs,
)

console = Console()

DECISION_KEYS = {
    "k": Decision.KEEP,
    "f": Decision.FILTER_DELETE,
    "u": Decision.UNSUBSCRIBE,
    "s": Decision.SKIP,
}

DECISION_LABELS = {
    Decision.KEEP: "[green]Keep[/green]",
    Decision.FILTER_DELETE: "[red]Filter+Delete[/red]",
    Decision.UNSUBSCRIBE: "[red bold]Unsubscribe[/red bold]",
    Decision.SKIP: "[yellow]Skip[/yellow]",
}


def _decisions_path(account: str) -> Path:
    return DECISIONS_DIR / f"{account}.json"


def load_decisions(account: str) -> list[SenderDecision]:
    """Load saved decisions for an account."""
    ensure_dirs()
    path = _decisions_path(account)
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    return [SenderDecision.model_validate(d) for d in data]


def save_decisions(account: str, decisions: list[SenderDecision]) -> None:
    """Save decisions to disk."""
    ensure_dirs()
    path = _decisions_path(account)
    data = [d.model_dump(mode="json") for d in decisions]
    path.write_text(json.dumps(data, indent=2, default=str))


def _auto_recommend(sender: Sender) -> Decision | None:
    """Suggest a decision based on sender characteristics."""
    # Daily+ promos are almost always unsubscribe candidates
    if sender.category == "PROMOTIONS" and sender.frequency_estimate in ("daily+", "daily"):
        if sender.has_unsubscribe_header:
            return Decision.UNSUBSCRIBE
        return Decision.FILTER_DELETE

    # High-frequency promotions
    if sender.category == "PROMOTIONS" and sender.message_count >= 10:
        return Decision.FILTER_DELETE

    # Social notifications that are frequent
    if sender.category == "SOCIAL" and sender.frequency_estimate in ("daily+", "daily"):
        return Decision.FILTER_DELETE

    return None


def _render_sender_panel(sender: Sender, index: int, total: int, recommendation: Decision | None = None) -> Panel:
    """Render a Rich panel for a sender."""
    header = f"{sender.display_name} <{sender.email}>" if sender.display_name else sender.email

    lines = []
    lines.append(f"[bold]{sender.message_count}[/bold] emails in scan period (~{sender.frequency_estimate})")
    if sender.category:
        lines.append(f"Category: [cyan]{sender.category}[/cyan]")
    for subj in sender.sample_subjects[:3]:
        lines.append(f'  [dim]"{subj}"[/dim]')
    unsub_mark = "[green]yes[/green]" if sender.has_unsubscribe_header else "[red]no[/red]"
    lines.append(f"Unsubscribe header: {unsub_mark}")

    body = "\n".join(lines)

    actions = "  [bold]\\[k][/bold] Keep  [bold]\\[f][/bold] Filter+Delete  [bold]\\[u][/bold] Unsub  [bold]\\[s][/bold] Skip"
    if recommendation:
        rec_label = DECISION_LABELS[recommendation]
        actions += f"  │  Suggested: {rec_label}"

    body += f"\n\n{actions}"

    return Panel(
        body,
        title=f"[bold]{header}[/bold]  ({index}/{total})",
        border_style="blue",
    )


def run_triage(scan_result: ScanResult, account: str, auto_recommend_flag: bool = False) -> list[SenderDecision]:
    """Run interactive triage session.

    Presents each sender and collects user decisions.
    Returns the list of all decisions (including previously saved ones).
    """
    existing_decisions = load_decisions(account)
    decided_emails = {d.sender.email for d in existing_decisions if d.decision != Decision.SKIP}

    # Filter to undecided senders
    pending_senders = [s for s in scan_result.senders if s.email not in decided_emails]

    if not pending_senders:
        console.print("[green]All senders have been triaged![/green]")
        return existing_decisions

    console.print(
        f"\n[bold]{len(pending_senders)}[/bold] senders to triage "
        f"({len(decided_emails)} already decided)\n"
    )

    new_decisions: list[SenderDecision] = []
    all_decisions = list(existing_decisions)

    for i, sender in enumerate(pending_senders, 1):
        recommendation = _auto_recommend(sender) if auto_recommend_flag else None
        panel = _render_sender_panel(sender, i, len(pending_senders), recommendation)
        console.print(panel)

        while True:
            prompt = "Your choice"
            if recommendation:
                default_key = {v: k for k, v in DECISION_KEYS.items()}[recommendation]
                prompt += f" [{default_key}]"

            choice = console.input(f"  {prompt}: ").strip().lower()

            # Handle default (enter with recommendation)
            if not choice and recommendation:
                decision = recommendation
                break

            if choice in DECISION_KEYS:
                decision = DECISION_KEYS[choice]
                break

            console.print("  [red]Invalid choice.[/red] Use k/f/u/s")

        sd = SenderDecision(
            sender=sender,
            decision=decision,
            decided_at=datetime.now(timezone.utc),
        )
        new_decisions.append(sd)
        all_decisions.append(sd)

        label = DECISION_LABELS[decision]
        console.print(f"  → {label}\n")

        # Save after each decision so progress isn't lost
        save_decisions(account, all_decisions)

    # Summary
    counts = {}
    for d in new_decisions:
        counts[d.decision] = counts.get(d.decision, 0) + 1

    console.print("[bold]Session summary:[/bold]")
    for decision, count in sorted(counts.items(), key=lambda x: x[1], reverse=True):
        console.print(f"  {DECISION_LABELS[decision]}: {count}")

    return all_decisions
