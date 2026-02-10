Review pending candidates for the Bluesky Earth Scientists list.

## Instructions

1. Read `bsky-list-manager/data/candidates.json`
2. Filter to candidates with `"status": "pending"`
3. If no pending candidates, report that and stop

4. For each pending candidate, display:
   - Handle, display name, bio
   - Categories, entity type, confidence
   - Source (how they were discovered: dm_request, network_crawl, manual_fetch, etc.)
   - If `recent_posts` field exists, review the posts for earth science relevance
   - If `dm_summary` field exists, show the DM context
   - Relevance assessment based on bio and available post history

5. For each candidate, recommend one of:
   - **approve** — add to the list (relevant earth scientist/institution)
   - **reject** — not relevant to the list
   - **defer** — uncertain, needs more information

6. Present candidates in groups of ~10 and ask for my confirmation before proceeding.

7. After I confirm decisions, update candidates.json:
   - Set `"status": "approved"` or `"status": "rejected"` or leave as `"pending"`
   - Add a `"reviewed_date"` field with today's date

8. For approved candidates, remind me to run `bsky-geo add <handle>` to actually add them to the Bluesky list.

## Candidate Record Fields

```json
{
  "handle": "someone.bsky.social",
  "display_name": "Dr Someone",
  "bio": "Geophysicist at ...",
  "categories": [],
  "entity_type": "",
  "institution": "",
  "confidence": 0.0,
  "source": "network_crawl",
  "status": "pending",
  "recent_posts": ["Just published a paper on...", "Great talk at AGU..."],
  "dm_summary": "(only for dm_request source)",
  "member_follow_count": 5,
  "discovered_date": "2025-01-15"
}
```
