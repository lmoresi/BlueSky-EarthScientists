"""CLI entry point for the Bluesky Earth Scientists list manager."""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

from . import data_store
from .bsky_client import BskyClient

console = Console()

# Load .env from the project root (next to pyproject.toml)
_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(_env_path)


def _get_client() -> BskyClient:
    """Create an authenticated BskyClient from env vars or config."""
    handle = os.environ.get("BSKY_HANDLE", "")
    password = os.environ.get("BSKY_APP_PASSWORD", "")
    if not handle or not password:
        console.print(
            "[red]BSKY_HANDLE and BSKY_APP_PASSWORD must be set.[/red]\n"
            "Set them in your environment or in a .env file.\n"
            "Run [bold]bsky-geo init[/bold] for setup help."
        )
        sys.exit(1)
    try:
        return BskyClient(handle, password)
    except Exception as exc:
        console.print(f"[red]Login failed: {exc}[/red]")
        sys.exit(1)


def _get_list_uri() -> str:
    """Get the list URI from config."""
    config = data_store.load_config()
    uri = config.get("list_uri", "")
    if not uri:
        console.print(
            "[red]No list configured.[/red] Run [bold]bsky-geo init[/bold] first."
        )
        sys.exit(1)
    return uri


@click.group()
def cli():
    """Bluesky Earth Scientists list manager.

    Sync follows, discover candidates, and manage a curated Bluesky list
    of earth science researchers and institutions.
    """
    pass


# ── init ────────────────────────────────────────────────────────────────────

@cli.command()
def init():
    """Set up the list manager: verify credentials, pick a list, bootstrap data."""
    data_store.ensure_data_dir()

    console.print("[bold]Bluesky Earth Scientists List Manager — Setup[/bold]\n")

    # Check for credentials
    handle = os.environ.get("BSKY_HANDLE", "")
    password = os.environ.get("BSKY_APP_PASSWORD", "")

    if not handle or not password:
        console.print(
            "Set your credentials as environment variables or in a .env file:\n"
            "  BSKY_HANDLE=yourhandle.bsky.social\n"
            "  BSKY_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx\n"
        )
        handle = click.prompt("Bluesky handle", default=handle)
        password = click.prompt("App password", default=password, hide_input=True)

    # Login
    console.print(f"\nLogging in as [bold]{handle}[/bold]...")
    try:
        client = BskyClient(handle, password)
    except Exception as exc:
        console.print(f"[red]Login failed: {exc}[/red]")
        sys.exit(1)
    console.print(f"[green]Logged in as {client.profile.handle} ({client.did})[/green]\n")

    # Pick a list
    console.print("Fetching your lists...")
    lists = client.get_lists()

    if not lists:
        console.print("[yellow]No lists found. Create a list on Bluesky first.[/yellow]")
        list_uri = click.prompt("Enter list URI manually")
    else:
        console.print("\nYour lists:")
        for i, lst in enumerate(lists, 1):
            console.print(f"  {i}. {lst['name']} — {lst['description'][:60]}")
            console.print(f"     URI: {lst['uri']}")

        choice = click.prompt(
            "\nSelect a list number (or paste a URI)",
            default="1",
        )

        if choice.startswith("at://"):
            list_uri = choice
        else:
            idx = int(choice) - 1
            if 0 <= idx < len(lists):
                list_uri = lists[idx]["uri"]
            else:
                console.print("[red]Invalid selection.[/red]")
                sys.exit(1)

    # Bootstrap: pull current list members
    console.print(f"\nFetching current list members...")
    raw_members = client.get_list_members(list_uri)
    console.print(f"Found {len(raw_members)} members on the list.")

    members = data_store.load_members()
    added = 0
    for m in raw_members:
        did = m["did"]
        if did not in members:
            members[did] = {
                "handle": m["handle"],
                "display_name": m.get("display_name", ""),
                "bio": None,
                "categories": [],
                "entity_type": "",
                "institution": "",
                "added_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "source": "init_bootstrap",
                "confidence": 1.0,
                "listitem_uri": m.get("listitem_uri", ""),
                "notes": "",
            }
            added += 1

    data_store.save_members(members)

    # Save config
    config = data_store.load_config()
    config.update({
        "list_uri": list_uri,
        "account_did": client.did,
        "account_handle": client.profile.handle,
        "initialized_at": datetime.now(timezone.utc).isoformat(),
        "categories": [
            "geodynamics", "seismology", "volcanology", "petrology",
            "mineralogy", "geochemistry", "paleontology", "geomorphology",
            "hydrogeology", "planetary", "geophysics", "tectonics",
            "sedimentology", "glaciology", "geodesy", "stratigraphy",
            "marine_geology", "environmental_science", "climate_science",
            "atmospheric_science", "oceanography", "ecology", "sustainability",
            "natural_hazards", "remote_sensing", "engineering_geology", "other",
        ],
        "entity_types": [
            "individual", "institution", "department", "society", "journal",
            "podcast", "service", "bot",
        ],
    })
    data_store.save_config(config)

    console.print(f"\n[green]Setup complete![/green]")
    console.print(f"  List URI: {list_uri}")
    console.print(f"  Members bootstrapped: {added} new, {len(raw_members)} total on list")
    console.print(f"\nNext step: run [bold]bsky-geo sync-follows[/bold] to sync your follows to the list.")
    console.print(
        "\n[dim]Tip: For DM checking, ensure your app password has DM access enabled "
        "(Settings > App Passwords).[/dim]"
    )


# ── sync-follows ────────────────────────────────────────────────────────────

@cli.command("sync-follows")
def sync_follows():
    """Sync your follows to the list — add any followed accounts not yet on the list."""
    client = _get_client()
    list_uri = _get_list_uri()

    console.print("[bold]Syncing follows to list...[/bold]\n")

    # Backup before mutations
    data_store.backup("members.json")

    # Fetch follows and list members
    console.print("Fetching follows...")
    follows = client.get_all_follows()
    follow_dids = {f["did"] for f in follows}
    follow_map = {f["did"]: f for f in follows}
    console.print(f"  {len(follows)} follows")

    console.print("Fetching list members...")
    list_members = client.get_list_members(list_uri)
    list_dids = {m["did"] for m in list_members}
    console.print(f"  {len(list_members)} list members\n")

    members = data_store.load_members()

    # Follows NOT on list — add them
    to_add = follow_dids - list_dids
    added = 0
    errors = 0

    if to_add:
        console.print(f"Adding {len(to_add)} followed accounts to list...")
        for did in to_add:
            info = follow_map[did]
            try:
                listitem_uri = client.add_to_list(list_uri, did)
                members[did] = {
                    "handle": info["handle"],
                    "display_name": info.get("display_name", ""),
                    "bio": info.get("description", ""),
                    "categories": [],
                    "entity_type": "",
                    "institution": "",
                    "added_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    "source": "follow_sync",
                    "confidence": 1.0,
                    "listitem_uri": listitem_uri,
                    "notes": "",
                }
                added += 1
                console.print(f"  [green]+[/green] {info['handle']}")
            except Exception as exc:
                errors += 1
                console.print(f"  [red]Error adding {info['handle']}: {exc}[/red]")

        data_store.save_members(members)

    # List members NOT followed — auto-follow them (list is the master copy)
    on_list_not_followed = list_dids - follow_dids
    followed = 0
    follow_errors = 0
    if on_list_not_followed:
        console.print(f"Following {len(on_list_not_followed)} list members not yet followed...")
        for m in list_members:
            if m["did"] in on_list_not_followed:
                try:
                    client.follow(m["did"])
                    followed += 1
                    console.print(f"  [blue]+[/blue] {m['handle']} ({m.get('display_name', '')})")
                except Exception as exc:
                    follow_errors += 1
                    console.print(f"  [red]Error following {m['handle']}: {exc}[/red]")

    # Update listitem URIs for existing members
    for m in list_members:
        if m["did"] in members and not members[m["did"]].get("listitem_uri"):
            members[m["did"]]["listitem_uri"] = m.get("listitem_uri", "")
    data_store.save_members(members)

    # Summary
    already = follow_dids & list_dids
    console.print(f"\n[bold]Sync complete:[/bold]")
    console.print(f"  [green]{added} added to list[/green]")
    if followed:
        console.print(f"  [blue]{followed} now followed[/blue]")
    if errors or follow_errors:
        console.print(f"  [red]{errors + follow_errors} errors[/red]")
    console.print(f"  {len(already)} already synced")


# ── add ─────────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("handle_or_did")
@click.option("--follow/--no-follow", default=True, help="Also follow the account (default: yes).")
def add(handle_or_did: str, follow: bool):
    """Add a single account to the list (and follow them)."""
    client = _get_client()
    list_uri = _get_list_uri()

    console.print(f"Resolving {handle_or_did}...")
    profile = client.get_profile(handle_or_did)
    did = profile["did"]
    handle = profile["handle"]

    members = data_store.load_members()
    if did in members:
        console.print(f"[yellow]{handle} is already a member.[/yellow]")
        return

    console.print(f"Adding [bold]{profile['display_name']}[/bold] (@{handle}) to list...")

    data_store.backup("members.json")

    try:
        listitem_uri = client.add_to_list(list_uri, did)
    except Exception as exc:
        console.print(f"[red]Error adding to list: {exc}[/red]")
        return

    members[did] = {
        "handle": handle,
        "display_name": profile.get("display_name", ""),
        "bio": profile.get("description", ""),
        "categories": [],
        "entity_type": "",
        "institution": "",
        "added_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "source": "manual",
        "confidence": 1.0,
        "listitem_uri": listitem_uri,
        "notes": "",
    }
    data_store.save_members(members)

    if follow:
        try:
            client.follow(did)
            console.print(f"  [green]Followed {handle}[/green]")
        except Exception as exc:
            console.print(f"  [yellow]Follow failed: {exc}[/yellow]")

    console.print(f"[green]Added {handle} to list.[/green]")


# ── bulk-add ───────────────────────────────────────────────────────────────

@cli.command("bulk-add")
@click.option("--delay", default=1.0, help="Seconds between API calls (default: 1.0).")
@click.option("--dry-run", is_flag=True, help="Show what would be added without doing it.")
def bulk_add(delay: float, dry_run: bool):
    """Add all approved candidates to the list in bulk."""
    candidates = data_store.load_candidates()
    members = data_store.load_members()

    approved = {
        did: info for did, info in candidates.items()
        if info.get("status") == "approved" and did not in members
    }

    # Also skip any already-on-list (removed then re-approved)
    approved = {
        did: info for did, info in approved.items()
        if not (did in members and not members[did].get("removed"))
    }

    if not approved:
        console.print("[green]No approved candidates to add.[/green]")
        return

    console.print(
        f"[bold]Bulk-adding {len(approved)} approved candidates to list[/bold]"
    )

    if dry_run:
        for did, info in approved.items():
            console.print(f"  [dim]Would add:[/dim] {info.get('handle', did)}")
        console.print(f"\n[yellow]Dry run — no changes made.[/yellow]")
        return

    client = _get_client()
    list_uri = _get_list_uri()
    data_store.backup("members.json")

    added = 0
    errors = 0

    for i, (did, info) in enumerate(approved.items(), 1):
        handle = info.get("handle", did)
        try:
            listitem_uri = client.add_to_list(list_uri, did)

            members[did] = {
                "handle": handle,
                "display_name": info.get("display_name", ""),
                "bio": info.get("bio", ""),
                "categories": info.get("categories", []),
                "entity_type": info.get("entity_type", ""),
                "institution": info.get("institution", ""),
                "added_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "source": info.get("source", "candidate"),
                "confidence": info.get("confidence", 0.0),
                "listitem_uri": listitem_uri,
                "notes": "",
            }

            # Also follow
            try:
                client.follow(did)
            except Exception:
                pass  # Already following or follow failed — not critical

            candidates[did]["status"] = "added"
            added += 1
            console.print(f"  [{i}/{len(approved)}] [green]+[/green] {handle}")

            # Save periodically (every 25) so progress isn't lost on crash
            if added % 25 == 0:
                data_store.save_members(members)
                data_store.save_candidates(candidates)

        except Exception as exc:
            errors += 1
            console.print(f"  [{i}/{len(approved)}] [red]Error: {handle} — {exc}[/red]")

        time.sleep(delay)

    # Final save
    data_store.save_members(members)
    data_store.save_candidates(candidates)

    console.print(f"\n[bold]Bulk add complete:[/bold]")
    console.print(f"  [green]{added} added to list[/green]")
    if errors:
        console.print(f"  [red]{errors} errors[/red]")


# ── remove ──────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("handle_or_did")
def remove(handle_or_did: str):
    """Remove an account from the list."""
    client = _get_client()
    list_uri = _get_list_uri()

    # Resolve to DID
    console.print(f"Resolving {handle_or_did}...")
    profile = client.get_profile(handle_or_did)
    did = profile["did"]
    handle = profile["handle"]

    members = data_store.load_members()

    # Find the listitem URI
    listitem_uri = None
    if did in members:
        listitem_uri = members[did].get("listitem_uri", "")

    if not listitem_uri:
        # Look it up from the list directly
        console.print("Looking up list membership...")
        list_members = client.get_list_members(list_uri)
        for m in list_members:
            if m["did"] == did:
                listitem_uri = m["listitem_uri"]
                break

    if not listitem_uri:
        console.print(f"[yellow]{handle} is not on the list.[/yellow]")
        return

    data_store.backup("members.json")

    console.print(f"Removing [bold]{handle}[/bold] from list...")
    try:
        client.remove_from_list(listitem_uri)
    except Exception as exc:
        console.print(f"[red]Error removing from list: {exc}[/red]")
        return

    # Soft delete: keep in members but mark as removed
    if did in members:
        members[did]["removed"] = True
        members[did]["removed_date"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        members[did]["listitem_uri"] = ""
        data_store.save_members(members)

    console.print(f"[green]Removed {handle} from list.[/green]")


# ── list ────────────────────────────────────────────────────────────────────

@cli.command("list")
@click.option("--category", "-c", help="Filter by category.")
@click.option("--type", "-t", "entity_type", help="Filter by entity type.")
@click.option("--source", "-s", help="Filter by source.")
@click.option("--no-bots", is_flag=True, help="Exclude accounts flagged as bots.")
@click.option("--stats", is_flag=True, help="Show summary statistics.")
def list_members(category: str | None, entity_type: str | None, source: str | None, no_bots: bool, stats: bool):
    """Show current list members."""
    members = data_store.load_members()

    # Filter out removed members
    active = {
        did: info for did, info in members.items()
        if not info.get("removed")
    }

    if category:
        active = {
            did: info for did, info in active.items()
            if category.lower() in [c.lower() for c in info.get("categories", [])]
        }
    if entity_type:
        active = {
            did: info for did, info in active.items()
            if info.get("entity_type", "").lower() == entity_type.lower()
        }
    if source:
        active = {
            did: info for did, info in active.items()
            if info.get("source", "").lower() == source.lower()
        }
    if no_bots:
        active = {
            did: info for did, info in active.items()
            if not info.get("is_bot")
        }

    if stats:
        _show_stats(active)
        return

    if not active:
        console.print("[yellow]No members match the filters.[/yellow]")
        return

    table = Table(title=f"List Members ({len(active)})")
    table.add_column("Handle", style="cyan")
    table.add_column("Name")
    table.add_column("Categories", style="green")
    table.add_column("Type", style="blue")
    table.add_column("Source", style="dim")
    table.add_column("Added", style="dim")

    for did, info in sorted(active.items(), key=lambda x: x[1].get("handle", "")):
        table.add_row(
            info.get("handle", ""),
            info.get("display_name", ""),
            ", ".join(info.get("categories", [])[:3]),
            info.get("entity_type", ""),
            info.get("source", ""),
            info.get("added_date", ""),
        )

    console.print(table)


def _show_stats(members: dict) -> None:
    """Show summary statistics for members."""
    from collections import Counter

    total = len(members)
    bot_count = sum(1 for info in members.values() if info.get("is_bot"))
    by_source = Counter(info.get("source", "unknown") for info in members.values())
    by_type = Counter(
        (info.get("entity_type") or "unclassified") for info in members.values()
    )

    cat_counter: Counter = Counter()
    for info in members.values():
        for cat in info.get("categories", []):
            cat_counter[cat] += 1

    console.print(f"\n[bold]Members: {total}[/bold]")
    if bot_count:
        console.print(f"  Flagged as bots: {bot_count}")
    console.print()

    table = Table(title="By Source")
    table.add_column("Source")
    table.add_column("Count", justify="right")
    for src, count in by_source.most_common():
        table.add_row(src, str(count))
    console.print(table)

    table = Table(title="By Entity Type")
    table.add_column("Type")
    table.add_column("Count", justify="right")
    for t, count in by_type.most_common():
        table.add_row(t, str(count))
    console.print(table)

    if cat_counter:
        table = Table(title="By Category")
        table.add_column("Category")
        table.add_column("Count", justify="right")
        for cat, count in cat_counter.most_common(20):
            table.add_row(cat, str(count))
        console.print(table)


# ── fetch-profile ──────────────────────────────────────────────────────────

@cli.command("fetch-profile")
@click.argument("handle_or_did")
def fetch_profile(handle_or_did: str):
    """Fetch a profile and recent posts from Bluesky, save as a pending candidate."""
    client = _get_client()

    console.print(f"Fetching profile for {handle_or_did}...")
    profile = client.get_profile(handle_or_did)
    did = profile["did"]
    handle = profile["handle"]

    # Check if already known
    members = data_store.load_members()
    if did in members and not members[did].get("removed"):
        console.print(f"[yellow]{handle} is already a member.[/yellow]")
        return

    console.print(f"Fetching recent posts from @{handle}...")
    posts = client.get_author_posts(did, limit=20)
    console.print(f"  {len(posts)} posts retrieved")

    # Save to candidates
    candidates = data_store.load_candidates()
    candidates[did] = {
        "handle": handle,
        "display_name": profile.get("display_name", ""),
        "bio": profile.get("description", ""),
        "categories": [],
        "entity_type": "",
        "institution": "",
        "confidence": 0.0,
        "source": "manual_fetch",
        "status": "pending",
        "recent_posts": posts[:20],
        "discovered_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }
    data_store.save_candidates(candidates)

    # Display profile summary
    console.print(f"\n[bold]{profile.get('display_name', '')}[/bold] (@{handle})")
    bio = profile.get("description", "")
    if bio:
        console.print(f"  Bio: {bio[:200]}")
    console.print(f"  Followers: {profile.get('followers_count', 0)}")
    console.print(f"  Posts: {profile.get('posts_count', 0)}")
    console.print(f"\n[green]Saved to candidates as pending.[/green]")
    console.print(f"[dim]Run /evaluate {handle} for an AI assessment.[/dim]")


# ── refresh-profiles ────────────────────────────────────────────────────────

@cli.command("refresh-profiles")
@click.option("--all", "refresh_all", is_flag=True, help="Refresh all members (default: only those with empty bios).")
def refresh_profiles(refresh_all: bool):
    """Batch-fetch fresh profiles from Bluesky and update members.json.

    By default, only refreshes members with empty bios. Use --all to
    refresh every member. This is fast (25 profiles per API call) and
    does not use AI — it's a pure Bluesky API operation.
    """
    from rich.progress import BarColumn, MofNCompleteColumn, Progress, TextColumn

    client = _get_client()
    members = data_store.load_members()

    # Filter to active members
    active = {
        did: info for did, info in members.items()
        if not info.get("removed")
    }

    if refresh_all:
        to_refresh = active
    else:
        to_refresh = {
            did: info for did, info in active.items()
            if info.get("bio") is None
        }

    if not to_refresh:
        console.print("[green]All members already have profile data.[/green]")
        return

    console.print(
        f"[bold]Refreshing {len(to_refresh)} profiles "
        f"({'all' if refresh_all else 'empty bios only'})...[/bold]"
    )

    data_store.backup("members.json")

    # Batch in groups of 25 (API limit)
    items = list(to_refresh.keys())
    batches = [items[i:i + 25] for i in range(0, len(items), 25)]
    updated = 0
    errors = 0

    console.print(f"  {len(batches)} batches of up to 25\n")

    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Fetching profiles", total=len(items))

        for batch_dids in batches:
            try:
                profiles = client.get_profiles(batch_dids)
                profile_map = {p["did"]: p for p in profiles}
            except Exception as exc:
                console.print(f"  [yellow]Batch fetch failed: {exc}[/yellow]")
                errors += len(batch_dids)
                progress.advance(task, len(batch_dids))
                continue

            for did in batch_dids:
                if did in profile_map:
                    p = profile_map[did]
                    members[did]["handle"] = p.get("handle", members[did].get("handle", ""))
                    members[did]["display_name"] = p.get("display_name", "")
                    members[did]["bio"] = p.get("description", "")
                    updated += 1
                else:
                    errors += 1
                progress.advance(task)

    data_store.save_members(members)

    console.print(f"\n[bold]Profile refresh complete:[/bold]")
    console.print(f"  [green]{updated} profiles updated[/green]")
    if errors:
        console.print(f"  [red]{errors} failed (deleted/suspended accounts)[/red]")


# ── check-dms ───────────────────────────────────────────────────────────────

@cli.command("check-dms")
def check_dms():
    """Check DMs for list addition requests."""
    client = _get_client()

    console.print("[bold]Checking DMs for list addition requests...[/bold]\n")

    try:
        convos = client.get_dm_conversations(limit=50)
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        return

    if not convos:
        console.print("[yellow]No DM conversations found.[/yellow]")
        return

    console.print(f"Found {len(convos)} conversations. Scanning for requests...\n")

    # Keywords that suggest a list addition request
    REQUEST_KEYWORDS = ["add me", "join", "list", "earth scien", "geolog", "member"]

    candidates = data_store.load_candidates()
    members = data_store.load_members()
    new_requests = []

    for convo in convos:
        # Get messages from conversation
        try:
            messages = client.get_dm_messages(convo["id"], limit=20)
        except Exception:
            continue

        if not messages:
            continue

        # Build conversation text and check for keywords
        convo_text = ""
        for msg in messages:
            sender = msg.get("sender_did", "unknown")
            role = "them" if sender != client.did else "me"
            convo_text += f"[{role}]: {msg.get('text', '')}\n"

        # Simple keyword heuristic for request detection
        convo_lower = convo_text.lower()
        is_request = any(kw in convo_lower for kw in REQUEST_KEYWORDS)

        if not is_request:
            continue

        # Identify the requester
        other_members = [
            m for m in convo["members"] if m["did"] != client.did
        ]
        if not other_members:
            continue

        requester = other_members[0]
        did = requester["did"]

        if did in members or did in candidates:
            console.print(
                f"  [dim]Skipping {requester['handle']} — already known[/dim]"
            )
            continue

        # Fetch profile and recent posts
        console.print(f"  Fetching {requester['handle']}...")
        try:
            profile = client.get_profile(did)
            posts = client.get_author_posts(did, limit=20)

            # Truncate DM summary for storage
            dm_summary = convo_text[:500]

            candidates[did] = {
                "handle": requester["handle"],
                "display_name": requester.get("display_name", ""),
                "bio": profile.get("description", ""),
                "categories": [],
                "entity_type": "",
                "institution": "",
                "confidence": 0.0,
                "source": "dm_request",
                "status": "pending",
                "dm_summary": dm_summary,
                "recent_posts": posts[:20],
                "discovered_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            }
            new_requests.append(requester["handle"])

            bio = profile.get("description", "") or ""
            console.print(f"    {bio[:80]}")

        except Exception as exc:
            console.print(f"    [yellow]Error: {exc}[/yellow]")

    if new_requests:
        data_store.save_candidates(candidates)
        console.print(
            f"\n[green]{len(new_requests)} new DM requests added to review queue:[/green]"
        )
        for h in new_requests:
            console.print(f"  • {h}")
        console.print(
            "\n[dim]Run /review-candidates to evaluate and approve/reject them.[/dim]"
        )
    else:
        console.print("[yellow]No new addition requests found in DMs.[/yellow]")


# ── crawl ───────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--threshold", "-t", default=3, help="Minimum members following an account.")
@click.option("--max-fetch", "-n", default=50, help="Max candidates to fetch profiles for.")
@click.option(
    "--strategy", default="all",
    type=click.Choice(["all", "institutions", "weighted"]),
    help="Crawl strategy: all (default), institutions (only), or weighted (institutions count 2x).",
)
def crawl(threshold: int, max_fetch: int, strategy: str):
    """Discover candidate earth scientists from member networks."""
    client = _get_client()
    members = data_store.load_members()
    candidates = data_store.load_candidates()

    # Filter to active members only
    active_members = {
        did: info for did, info in members.items()
        if not info.get("removed")
    }

    if not active_members:
        console.print("[yellow]No members to crawl. Run init and sync-follows first.[/yellow]")
        return

    from .crawler import crawl_network

    data_store.backup("candidates.json")

    crawl_network(
        client,
        active_members,
        candidates,
        frequency_threshold=threshold,
        max_fetch=max_fetch,
        strategy=strategy,
    )


# ── review ──────────────────────────────────────────────────────────────────

@cli.command()
def review():
    """Interactive review of pending candidates."""
    client = _get_client()
    list_uri = _get_list_uri()

    from .review_ui import review_candidates

    review_candidates(client, list_uri)


# ── help ────────────────────────────────────────────────────────────────────

@cli.command("help")
def help_cmd():
    """Getting started guide — how to set up credentials and use the tool."""
    console.print("[bold]Bluesky Earth Scientists List Manager[/bold]")
    console.print("Manage a curated Bluesky list of earth science researchers and institutions.\n")

    console.print("[bold underline]1. Create a Bluesky App Password[/bold underline]\n")
    console.print("  Go to Bluesky > Settings > Advanced > App Passwords")
    console.print("  Click [bold]Add App Password[/bold], give it a name (e.g. \"list-manager\")")
    console.print("  [yellow]Important:[/yellow] tick [bold]\"Allow access to your direct messages\"[/bold]")
    console.print("  if you want the check-dms command to work.")
    console.print("  Copy the generated password (format: xxxx-xxxx-xxxx-xxxx).\n")

    console.print("[bold underline]2. Store your credentials[/bold underline]\n")
    console.print("  [bold]Option A[/bold] — .env file (recommended):")
    console.print("  Create a file called [cyan].env[/cyan] in the bsky-list-manager/ directory:\n")
    console.print("    BSKY_HANDLE=yourhandle.bsky.social")
    console.print("    BSKY_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx\n")
    console.print("  Or run [cyan]bsky-geo set-credentials[/cyan] to be prompted.\n")
    console.print("  [bold]Option B[/bold] — environment variables:")
    console.print("  export BSKY_HANDLE=yourhandle.bsky.social")
    console.print("  export BSKY_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx\n")
    console.print("  The .env file is git-ignored so your secrets stay local.\n")

    console.print("[bold underline]3. Initialise[/bold underline]\n")
    console.print("  [cyan]bsky-geo init[/cyan]")
    console.print("  This logs in, lets you pick which Bluesky list to manage,")
    console.print("  and bootstraps data/members.json from the current list members.\n")

    console.print("[bold underline]4. Typical workflow[/bold underline]\n")
    console.print("  [cyan]bsky-geo sync-follows[/cyan]        Sync your follows to the list")
    console.print("  [cyan]bsky-geo refresh-profiles[/cyan]    Update bios from Bluesky")
    console.print("  [cyan]bsky-geo add <handle>[/cyan]        Manually add someone")
    console.print("  [cyan]bsky-geo list --stats[/cyan]        See who's on the list")
    console.print("  [cyan]bsky-geo fetch-profile <h>[/cyan]   Fetch a profile for AI review")
    console.print("  [cyan]bsky-geo crawl[/cyan]               Discover candidates from networks")
    console.print("  [cyan]bsky-geo check-dms[/cyan]           Find DM requests to join\n")
    console.print("  AI tasks (classify, evaluate, review) use slash commands")
    console.print("  in Claude Code — no API key needed.\n")

    console.print("[bold underline]Troubleshooting[/bold underline]\n")
    console.print("  [cyan]bsky-geo doctor[/cyan]          Check credentials and data file health")
    console.print("  [cyan]bsky-geo set-credentials[/cyan] Update credentials if they've changed\n")


# ── doctor ──────────────────────────────────────────────────────────────────

@cli.command()
def doctor():
    """Diagnostic check — verify credentials, data files, and show help."""
    console.print("[bold]Bluesky Earth Scientists List Manager — Diagnostics[/bold]\n")

    # Check Bluesky credentials
    handle = os.environ.get("BSKY_HANDLE", "")
    password = os.environ.get("BSKY_APP_PASSWORD", "")
    if handle and password:
        try:
            client = BskyClient(handle, password)
            console.print(f"Credentials:   [green]OK[/green] (logged in as {client.profile.handle})")
        except Exception as exc:
            console.print(f"Credentials:   [red]FAIL[/red] ({exc})")
    else:
        console.print("Credentials:   [red]NOT SET[/red] (set BSKY_HANDLE and BSKY_APP_PASSWORD)")

    # Check data files
    config = data_store.load_config()
    members = data_store.load_members()
    candidates = data_store.load_candidates()

    active_members = sum(1 for m in members.values() if not m.get("removed"))
    pending = sum(1 for c in candidates.values() if c.get("status") == "pending")

    if config:
        console.print(
            f"Data files:     [green]OK[/green] "
            f"(config.json, {active_members} members, {pending} pending candidates)"
        )
        if config.get("list_uri"):
            console.print(f"List URI:       {config['list_uri']}")
    else:
        console.print("Data files:     [yellow]NOT INITIALIZED[/yellow] (run bsky-geo init)")

    if config.get("initialized_at"):
        console.print(f"Initialized:    {config['initialized_at']}")

    # Command cheat sheet
    console.print("\n[bold]Commands:[/bold]")
    commands = [
        ("bsky-geo init", "Set up credentials and pick a list"),
        ("bsky-geo sync-follows", "Sync your follows to the list"),
        ("bsky-geo refresh-profiles", "Batch-fetch fresh bios (--all for everyone)"),
        ("bsky-geo add <handle>", "Add someone to the list"),
        ("bsky-geo remove <handle>", "Remove someone from the list"),
        ("bsky-geo list", "Show current members (--stats for summary)"),
        ("bsky-geo fetch-profile <h>", "Fetch profile + posts for AI review"),
        ("bsky-geo crawl", "Discover candidates from member networks"),
        ("bsky-geo check-dms", "Check DMs for addition requests"),
        ("bsky-geo set-credentials", "Update stored credentials"),
        ("bsky-geo doctor", "This diagnostic screen"),
    ]
    for cmd, desc in commands:
        console.print(f"  [cyan]{cmd:<30}[/cyan] {desc}")


# ── set-credentials ─────────────────────────────────────────────────────────

@cli.command("set-credentials")
def set_credentials():
    """Update stored Bluesky credentials in .env file."""
    env_path = Path(__file__).resolve().parent.parent.parent / ".env"

    # Load existing .env content
    env_vars = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                env_vars[key.strip()] = value.strip()

    handle = click.prompt("Bluesky handle", default=env_vars.get("BSKY_HANDLE", ""))
    password = click.prompt("App password", hide_input=True)

    # Test login
    console.print("Testing login...")
    try:
        client = BskyClient(handle, password)
        console.print(f"[green]Login successful as {client.profile.handle}[/green]")
        env_vars["BSKY_HANDLE"] = handle
        env_vars["BSKY_APP_PASSWORD"] = password
    except Exception as exc:
        console.print(f"[red]Login failed: {exc}[/red]")
        return

    # Write .env
    lines = [f"{k}={v}" for k, v in env_vars.items()]
    env_path.write_text("\n".join(lines) + "\n")
    console.print(f"[green]Credentials saved to {env_path}[/green]")


# ── Entry point ─────────────────────────────────────────────────────────────

def main():
    cli()
