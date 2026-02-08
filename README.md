# BlueSky Earth Scientists

Tools for managing a curated [Bluesky](https://bsky.app/) list of earth science researchers, institutions, and organisations.

The list feeds a community starter pack and feed covering geology, geophysics, climate science, oceanography, atmospheric science, ecology, environmental science, planetary science, and related disciplines.

## bsky-list-manager

A CLI tool and interactive [Claude Code](https://docs.anthropic.com/en/docs/claude-code) workflow for managing the list.

**CLI commands** handle Bluesky API operations — syncing follows, adding/removing members, fetching profiles, discovering candidates from member networks, and checking DMs for addition requests.

**Slash commands** handle AI tasks interactively in a Claude Code session — classifying members by entity type, reviewing candidates, generating statistics, identifying bots, and evaluating accounts for relevance.

### Setup

Requires [pixi](https://pixi.sh/) for environment management.

```bash
cd bsky-list-manager
pixi install
```

Create a `.env` file with your credentials:

```
BSKY_HANDLE=yourhandle.bsky.social
BSKY_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
ANTHROPIC_API_KEY=sk-ant-...
```

The Bluesky app password can be created at Settings > App Passwords (enable DM access if you want `check-dms` to work). The Anthropic API key is only needed for the scripted `evaluate` and `crawl` commands — the interactive slash commands use Claude Code directly.

### Quick Start

```bash
pixi run bsky-geo init              # First-time setup: pick a list
pixi run bsky-geo sync-follows      # Sync follows to the list
pixi run bsky-geo refresh-profiles  # Fetch bios from Bluesky
```

Then in a Claude Code session (`claude` from the `bsky-list-manager/` directory):

```
/classify unclassified    # Classify members by entity type
/list-stats               # Summary statistics
/find-bots                # Identify automated accounts
/review-candidates        # Review pending candidates
/evaluate someone.bsky.social  # Evaluate an account
```

### CLI Commands

| Command | Description |
|---------|-------------|
| `bsky-geo init` | First-time setup — verify credentials, pick a list |
| `bsky-geo sync-follows` | Sync follows to list (bidirectional) |
| `bsky-geo refresh-profiles [--all]` | Batch-fetch fresh bios from Bluesky |
| `bsky-geo add <handle>` | Add someone to the list |
| `bsky-geo remove <handle>` | Remove someone from the list |
| `bsky-geo list [--stats]` | Show members or summary statistics |
| `bsky-geo evaluate <handle>` | AI-evaluate an account (uses Anthropic API) |
| `bsky-geo classify [--all]` | Classify members by entity type (uses Anthropic API) |
| `bsky-geo crawl` | Discover candidates from member networks |
| `bsky-geo review` | Interactive terminal review of candidates |
| `bsky-geo check-dms` | Check DMs for addition requests |
| `bsky-geo doctor` | Diagnostic check |

### Data Files

All runtime data lives in `bsky-list-manager/data/` and is git-ignored (it contains personal account data):

- `members.json` — list members keyed by DID
- `candidates.json` — pending candidates keyed by DID
- `config.json` — list URI, account settings

## License

MIT
