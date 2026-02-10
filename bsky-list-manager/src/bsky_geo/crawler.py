"""Network discovery — crawl member follows to find candidate earth scientists."""

from __future__ import annotations

import time
from collections import Counter
from datetime import datetime, timezone

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from . import data_store
from .bsky_client import BskyClient

console = Console()

# Only save accounts followed by this many existing members
FREQUENCY_THRESHOLD = 3

# Max candidates to fetch per crawl run
MAX_FETCH = 50

# Entity types considered "institutional" for crawl strategies
INSTITUTIONAL_TYPES = {"institution", "department", "society", "journal", "service"}


def crawl_network(
    client: BskyClient,
    members: dict,
    candidates: dict,
    *,
    frequency_threshold: int = FREQUENCY_THRESHOLD,
    max_fetch: int = MAX_FETCH,
    strategy: str = "all",
) -> list[dict]:
    """Crawl the follow networks of existing members to discover candidates.

    Fetches profiles and recent posts for discovered accounts, saving them
    to candidates.json for later review via /review-candidates.

    Args:
        client: Authenticated BskyClient.
        members: Current members dict keyed by DID.
        candidates: Current candidates dict keyed by DID.
        frequency_threshold: Minimum number of members following an account to save it.
        max_fetch: Maximum candidates to fetch profiles for in this run.
        strategy: Crawl strategy — "all" (default), "institutions" (only institutional
            entity types), or "weighted" (all members, but institutional follows count 2x).

    Returns:
        List of new candidate dicts that were added.
    """
    known_dids = set(members.keys()) | set(candidates.keys())
    follow_counts: Counter = Counter()

    # Filter members based on strategy
    if strategy == "institutions":
        crawl_members = {
            did: info for did, info in members.items()
            if info.get("entity_type", "") in INSTITUTIONAL_TYPES
        }
        if not crawl_members:
            console.print(
                "[yellow]No institutional members found. "
                "Run /classify first.[/yellow]"
            )
            return []
    else:
        crawl_members = members

    member_list = list(crawl_members.items())
    console.print(
        f"[bold]Crawling follows of {len(member_list)} members"
        f" (strategy: {strategy})...[/bold]"
    )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Crawling...", total=len(member_list))

        for did, info in member_list:
            handle = info.get("handle", did)
            progress.update(task, description=f"Fetching follows of {handle}")

            # Check cache first
            cached = data_store.load_crawl_cache(did)
            if cached and cached.get("follows"):
                follows = cached["follows"]
            else:
                try:
                    follows_raw = client.get_all_follows(did)
                    follows = [f["did"] for f in follows_raw]
                    data_store.save_crawl_cache(did, {
                        "follows": follows,
                        "crawled_at": datetime.now(timezone.utc).isoformat(),
                    })
                except Exception as exc:
                    console.print(f"  [yellow]Skipping {handle}: {exc}[/yellow]")
                    follows = []
                    time.sleep(1)

            # Weighted strategy: institutional follows count 2x
            weight = 1
            if strategy == "weighted" and info.get("entity_type", "") in INSTITUTIONAL_TYPES:
                weight = 2

            for follow_did in follows:
                if follow_did not in known_dids:
                    follow_counts[follow_did] += weight

            progress.advance(task)

    # Filter by frequency threshold
    frequent = [
        (did, count)
        for did, count in follow_counts.most_common()
        if count >= frequency_threshold
    ]

    console.print(
        f"\n[bold]Found {len(frequent)} accounts followed by "
        f"{frequency_threshold}+ members[/bold]"
    )

    if not frequent:
        return []

    # Fetch profiles for top candidates
    to_fetch = frequent[:max_fetch]
    new_candidates = []

    console.print(f"[bold]Fetching profiles for top {len(to_fetch)} candidates...[/bold]\n")

    for i, (did, count) in enumerate(to_fetch, 1):
        try:
            profile = client.get_profile(did)
            handle = profile.get("handle", did)
            console.print(
                f"  [{i}/{len(to_fetch)}] {handle} "
                f"(followed by {count} members)"
            )

            posts = client.get_author_posts(did, limit=20)

            candidate = {
                "handle": handle,
                "display_name": profile.get("display_name", ""),
                "bio": profile.get("description", ""),
                "categories": [],
                "entity_type": "",
                "institution": "",
                "confidence": 0.0,
                "source": "network_crawl",
                "status": "pending",
                "member_follow_count": count,
                "recent_posts": posts[:20],
                "discovered_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            }

            candidates[did] = candidate
            new_candidates.append(candidate)

            bio_preview = (profile.get("description", "") or "")[:80]
            if bio_preview:
                console.print(f"    {bio_preview}")

            # Brief pause between API calls
            time.sleep(0.3)

        except Exception as exc:
            console.print(f"    [yellow]Error fetching {did}: {exc}[/yellow]")
            time.sleep(1)

    # Save updated candidates
    data_store.save_candidates(candidates)

    console.print(
        f"\n[bold]Crawl complete:[/bold] {len(new_candidates)} candidates saved"
    )
    console.print(
        "[dim]Run /review-candidates to evaluate and approve/reject them.[/dim]"
    )

    return new_candidates
