Generate summary statistics for the Bluesky Earth Scientists list.

## Instructions

1. Read `bsky-list-manager/data/members.json`
2. Filter out removed members (`"removed": true`)
3. Generate and display the following statistics:

### Overview
- Total active members
- Members with classification vs unclassified
- Total flagged as bots

### By Entity Type
Table showing count for each entity_type (individual, institution, department, society, journal, podcast, service, bot, unclassified)

### By Source
Table showing count for each source value (init_bootstrap, follow_sync, manual, crawl, dm_request, etc.)

### By Category (Top 20)
Table showing the most common categories across all members. Note: members can have multiple categories, so counts will sum to more than total members.

### Bot Summary
List any accounts flagged as `is_bot: true` with their handles

### Data Quality
- Members with empty bios (may need `bsky-geo refresh-profiles`)
- Members with no categories assigned
- Members with low classification confidence (< 0.5)

4. Also check `bsky-list-manager/data/candidates.json`:
   - Count of pending candidates
   - Count of approved/rejected candidates

Present everything in clear, well-formatted tables.
