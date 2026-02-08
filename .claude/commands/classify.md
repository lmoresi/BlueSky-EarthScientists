Classify members of the Bluesky Earth Scientists list by entity type and bot status.

## Arguments: $ARGUMENTS

Scope (default: "unclassified"):
- `unclassified` — only members without an entity_type set
- `all` — reclassify every active member
- `<handle>` — classify a single member by handle

## Instructions

1. Read the members file at `bsky-list-manager/data/members.json`
2. Filter to the requested scope (skip members with `"removed": true`)
3. For each member, determine:
   - **entity_type**: one of `individual`, `institution`, `department`, `society`, `journal`, `podcast`, `service`, `bot`
   - **is_bot**: `true` or `false`
   - **classify_confidence**: 0.0–1.0

4. Process in batches of ~50 members. For each batch:
   - Show a summary table of your classifications
   - Write results back to members.json immediately after each batch
   - Report progress (e.g. "Batch 1/25 complete, 50 classified")

5. After all batches, show a summary: counts by entity_type, total bots flagged

## Entity Type Definitions

- **individual**: A person — researcher, student, professor, postdoc, science communicator with real expertise
- **institution**: University, research institute, lab, government agency, geological survey, museum
- **department**: A university department or research group (e.g. "MIT EAPS", "Oxford Earth Sciences")
- **society**: Professional/academic society (AGU, EGU, GSA, RAS, etc.)
- **journal**: Academic journal, publisher, or publication account
- **podcast**: Science podcast or media show
- **service**: Monitoring service, data service, alert system (earthquake alerts, weather services)
- **bot**: Automated repost account, RSS bridge, hashtag spammer with no original content

## Bot Detection

Flag `is_bot: true` for:
- Automated earthquake/weather/natural-hazard alert feeds
- Accounts that only repost links with hashtag spam
- RSS-to-social bridges with no original commentary
- Accounts with no original content, only automated reposts

**NOT bots**: Institutional accounts that post curated content with editorial voice.

## Classification Data Available

Each member record has: `handle`, `display_name`, `bio`, `categories`, `entity_type`, `is_bot`, `source`

Use `handle`, `display_name`, and `bio` as the primary signals for classification. If bio is empty, do your best from handle and display_name alone, and set confidence lower.

## Writing Results

After classifying each batch, update the member records in members.json:
```python
member["entity_type"] = "individual"  # or other type
member["is_bot"] = False  # or True
member["classify_confidence"] = 0.85  # your confidence
```

Use the Read tool to load the JSON, update the relevant fields, and use the Write tool to save it back.
