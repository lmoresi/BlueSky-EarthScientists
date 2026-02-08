"""Rich-based interactive review UI for candidate earth scientists."""

from __future__ import annotations

from datetime import datetime, timezone

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

from . import data_store
from .bsky_client import BskyClient

console = Console()


def review_candidates(
    client: BskyClient,
    list_uri: str,
) -> dict:
    """Interactive review of pending candidates.

    Returns dict with counts: approved, rejected, skipped.
    """
    candidates = data_store.load_candidates()
    members = data_store.load_members()

    pending = [
        (did, info)
        for did, info in candidates.items()
        if info.get("status") == "pending"
    ]

    if not pending:
        console.print("[yellow]No pending candidates to review.[/yellow]")
        return {"approved": 0, "rejected": 0, "skipped": 0}

    # Sort by confidence (highest first)
    pending.sort(key=lambda x: x[1].get("confidence", 0), reverse=True)

    counts = {"approved": 0, "rejected": 0, "skipped": 0}
    total = len(pending)

    console.print(f"\n[bold]Reviewing {total} pending candidates[/bold]")
    console.print("Actions: [green]a[/green]pprove / [red]r[/red]eject / "
                   "[yellow]s[/yellow]kip / [blue]e[/blue]dit categories / "
                   "[dim]q[/dim]uit\n")

    # Back up before mutations
    data_store.backup("candidates.json")
    data_store.backup("members.json")

    for i, (did, info) in enumerate(pending, 1):
        _display_candidate(i, total, did, info)

        while True:
            action = Prompt.ask(
                "Action",
                choices=["a", "r", "s", "e", "q"],
                default="s",
            )

            if action == "a":
                # Approve: add to list and members
                try:
                    listitem_uri = client.add_to_list(list_uri, did)
                    members[did] = {
                        "handle": info.get("handle", ""),
                        "display_name": info.get("display_name", ""),
                        "bio": info.get("bio", ""),
                        "categories": info.get("categories", []),
                        "entity_type": info.get("entity_type", ""),
                        "institution": info.get("institution", ""),
                        "added_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                        "source": info.get("source", "review"),
                        "confidence": info.get("confidence", 0.0),
                        "listitem_uri": listitem_uri,
                        "notes": "",
                    }
                    candidates[did]["status"] = "approved"
                    counts["approved"] += 1
                    console.print(f"  [green]Added {info.get('handle', did)} to list[/green]\n")
                except Exception as exc:
                    console.print(f"  [red]Error adding to list: {exc}[/red]\n")
                break

            elif action == "r":
                candidates[did]["status"] = "rejected"
                counts["rejected"] += 1
                console.print(f"  [red]Rejected {info.get('handle', did)}[/red]\n")
                break

            elif action == "s":
                counts["skipped"] += 1
                console.print(f"  [yellow]Skipped[/yellow]\n")
                break

            elif action == "e":
                new_cats = Prompt.ask(
                    "Enter categories (comma-separated)",
                    default=", ".join(info.get("categories", [])),
                )
                info["categories"] = [c.strip() for c in new_cats.split(",") if c.strip()]
                candidates[did]["categories"] = info["categories"]
                console.print(f"  [blue]Categories updated: {info['categories']}[/blue]")
                # Don't break — let them continue to approve/reject/skip

            elif action == "q":
                console.print("\n[dim]Quitting review...[/dim]")
                data_store.save_candidates(candidates)
                data_store.save_members(members)
                return counts

    # Save final state
    data_store.save_candidates(candidates)
    data_store.save_members(members)

    console.print(
        f"\n[bold]Review complete:[/bold] "
        f"[green]{counts['approved']} approved[/green], "
        f"[red]{counts['rejected']} rejected[/red], "
        f"[yellow]{counts['skipped']} skipped[/yellow]"
    )

    return counts


def _display_candidate(index: int, total: int, did: str, info: dict) -> None:
    """Display a candidate's details for review."""
    confidence = info.get("confidence", 0)
    if confidence >= 0.8:
        conf_style = "green"
    elif confidence >= 0.5:
        conf_style = "yellow"
    else:
        conf_style = "red"

    relevant = info.get("is_relevant", False)
    rel_text = "[green]YES[/green]" if relevant else "[red]NO[/red]"

    title = f"[{index}/{total}] {info.get('handle', did)}"

    content = Text()
    content.append(f"Name:        {info.get('display_name', '')}\n")
    content.append(f"Handle:      {info.get('handle', did)}\n")
    content.append(f"DID:         {did}\n")
    content.append(f"Bio:         {info.get('bio', '')[:200]}\n")
    content.append(f"Categories:  {', '.join(info.get('categories', []))}\n")
    content.append(f"Entity type: {info.get('entity_type', '')}\n")
    content.append(f"Institution: {info.get('institution', '')}\n")
    content.append(f"Source:      {info.get('source', '')}\n")

    if info.get("member_follow_count"):
        content.append(f"Followed by: {info['member_follow_count']} members\n")

    # Use a separate Rich renderable for styled parts
    console.print(Panel(content, title=title, border_style="blue"))

    # Print styled fields outside the panel for color support
    conf_text = Text()
    conf_text.append("Confidence:  ")
    conf_text.append(f"{confidence:.0%}", style=conf_style)
    conf_text.append(f"  |  Relevant: ")
    console.print(conf_text, end="")
    console.print(rel_text)

    if info.get("reasoning"):
        console.print(f"[dim]Reasoning: {info['reasoning']}[/dim]")
    if info.get("activity_assessment"):
        console.print(f"[dim]Activity:  {info['activity_assessment']}[/dim]")

    console.print()
