# Bluesky Earth Scientists List Manager

A curated Bluesky list of earth science researchers, institutions, and organisations. This tool manages the list membership, discovers candidates, and classifies members.

## Repository Layout

```
BlueSky-EarthScientists/             ← repo root (Claude runs from here)
├── CLAUDE.md                        ← this file
├── .claude/commands/                ← slash commands for AI tasks
├── bsky-list-manager/               ← Python project (pixi environment)
│   ├── pyproject.toml               ← pixi config & Python package config
│   ├── src/bsky_geo/                ← CLI source code
│   ├── data/                        ← members.json, candidates.json (git-ignored)
│   ├── .env                         ← credentials (git-ignored)
│   └── tests/
└── README.md
```

**Important:** The pixi environment and `pyproject.toml` live inside `bsky-list-manager/`, not at the repo root. All CLI commands must be run from that directory:

```bash
cd bsky-list-manager && pixi run bsky-geo <command>
```

## Interactive Workflow

The preferred workflow uses **slash commands** for AI tasks (classification, review, evaluation) and the **CLI** for Bluesky API operations (fetching profiles, adding/removing members, syncing follows).

### Slash Commands (AI tasks — run in conversation)
- `/classify [all|unclassified|handle]` — classify members by entity type and bot status
- `/review-candidates` — review pending candidates interactively
- `/list-stats` — summary statistics for the list
- `/find-bots` — identify likely bots and automated accounts
- `/evaluate <handle>` — evaluate an account for relevance

### CLI Commands (Bluesky API operations)

Run from `bsky-list-manager/` via `cd bsky-list-manager && pixi run bsky-geo <command>`:

```
bsky-geo refresh-profiles [--all]   Batch-fetch fresh bios from Bluesky (fast, no AI)
bsky-geo sync-follows               Sync follows to list (bidirectional)
bsky-geo add <handle>               Add someone to the list
bsky-geo remove <handle>            Remove someone from the list
bsky-geo list [--stats]             Show members (or summary stats)
bsky-geo fetch-profile <handle>     Fetch profile + posts, save as pending candidate
bsky-geo crawl                      Discover candidates from member networks
bsky-geo check-dms                  Check DMs for addition requests
bsky-geo init                       First-time setup
bsky-geo doctor                     Diagnostic check
```

### Typical Session
1. `bsky-geo refresh-profiles` — update bios from Bluesky
2. `/classify unclassified` — classify new members in conversation
3. `/list-stats` — review the state of the list
4. `/find-bots` — review bot flagging
5. `bsky-geo crawl` — discover new candidates
6. `/review-candidates` — approve/reject candidates interactively

## Data Files

All in `bsky-list-manager/data/` (git-ignored, personal to operator):

- **`members.json`** — current list members keyed by DID. Each record:
  ```json
  {
    "handle": "someone.bsky.social",
    "display_name": "Dr Someone",
    "bio": "Geophysicist at ...",
    "categories": ["geophysics", "seismology"],
    "entity_type": "individual",
    "is_bot": false,
    "institution": "",
    "added_date": "2025-01-15",
    "source": "follow_sync",
    "confidence": 1.0,
    "classify_confidence": 0.9,
    "listitem_uri": "at://...",
    "notes": ""
  }
  ```

  The `bio` field uses `null` to mean "not yet fetched from Bluesky" and `""` for "fetched but genuinely empty". Run `bsky-geo refresh-profiles` to fetch unfetched bios.

- **`candidates.json`** — pending candidates keyed by DID. Has `status` field: pending/approved/rejected. Candidates may include a `recent_posts` field (list of up to 20 post texts) for slash commands to use during evaluation.

- **`config.json`** — list URI, account DID, category/entity_type definitions.

## Entity Type Definitions

| Type | Description |
|------|-------------|
| `individual` | Person — researcher, student, professor, postdoc, science communicator |
| `institution` | University, research institute, lab, government agency, geological survey, museum |
| `department` | University department or research group |
| `society` | Professional/academic society (AGU, EGU, GSA, etc.) |
| `journal` | Academic journal, publisher, or publication account |
| `podcast` | Science podcast or media show |
| `service` | Monitoring service, data service, alert system |
| `bot` | Automated repost account, RSS bridge, no original content |

## Subdiscipline Categories

geodynamics, seismology, volcanology, petrology, mineralogy, geochemistry, paleontology, geomorphology, hydrogeology, planetary_science, geophysics, tectonics, sedimentology, glaciology, geodesy, stratigraphy, marine_geology, environmental_science, climate_science, atmospheric_science, oceanography, ecology, sustainability, natural_hazards, remote_sensing, engineering_geology, other

## Relevance Criteria

**Belongs on the list:**
- Researchers actively working in earth, environmental, ocean, atmospheric, or planetary sciences
- Geoscience departments, geological surveys, environmental agencies, research institutes
- Relevant academic societies, journals, science publishers
- Science communicators with genuine expertise in these fields
- Earthquake/volcano/weather monitoring services and natural hazard agencies

**Does NOT belong:**
- Casual science enthusiasts with no professional connection
- Accounts that rarely post about earth/environmental science
- Pure policy/advocacy with no scientific content
- Rock music, rock climbing, crystal healing, mining industry, landscape photography without science

## Reading and Writing Data

When slash commands read/write `members.json` or `candidates.json`:
- Use the Read tool to load the JSON file
- Parse it as a dict keyed by DID
- Update the relevant fields
- Use the Write tool to save the full JSON back
- The files are in `bsky-list-manager/data/`

## Package Manager
- Uses **pixi** for environment management
- Run from `bsky-list-manager/`: `pixi install` to set up; `pixi run pytest` to test

## Environment Variables
Set in `bsky-list-manager/.env` (git-ignored): `BSKY_HANDLE`, `BSKY_APP_PASSWORD`
