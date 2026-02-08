Identify likely bots and automated accounts on the Bluesky Earth Scientists list.

## Instructions

1. Read `bsky-list-manager/data/members.json`
2. Filter to active members (not removed)

3. Scan every member and flag likely bots/automated accounts based on:

### Strong bot signals
- Handle contains "bot", "alert", "feed", "rss", "auto"
- Bio mentions "automated", "bot", "RSS", "feed", "alerts"
- Bio contains no human-written text (just links/hashtags)
- Already flagged as `is_bot: true` from prior classification

### Moderate bot signals
- Display name looks automated (all caps, excessive emoji/symbols)
- Bio is a single URL with no description
- Handle follows automated naming patterns (earthquake_xx, weather_xx)

### Context that makes it NOT a bot
- Institutional accounts with editorial voice
- Monitoring services that also post original analysis
- News accounts with human curation

4. Present findings in groups:
   - **Confirmed bots** (already flagged `is_bot: true`)
   - **Likely bots** (strong signals, recommend flagging)
   - **Possible bots** (moderate signals, need review)

5. For each flagged account, show: handle, display_name, bio snippet, and your reasoning

6. Ask me which ones to flag. Then update members.json:
   - Set `is_bot: true` for confirmed ones
   - Optionally set `entity_type: "bot"` if appropriate
   - Set `entity_type: "service"` for legitimate monitoring services

7. After updating, report how many were flagged
