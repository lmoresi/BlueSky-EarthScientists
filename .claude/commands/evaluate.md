Evaluate a Bluesky account for relevance to the Earth Scientists list.

## Arguments: $ARGUMENTS

The handle or DID of the account to evaluate.

## Instructions

1. First check if this account is already in `bsky-list-manager/data/members.json` or `bsky-list-manager/data/candidates.json`

2. If found in members.json, use the stored profile data (handle, display_name, bio, categories, entity_type). Report their current status.

3. If found in candidates.json, show their evaluation and current status (pending/approved/rejected).

4. If NOT found in either file, note that we only have the handle — a profile fetch would be needed. Suggest running `bsky-geo evaluate <handle>` for a full evaluation with post history, or `bsky-geo add <handle>` to add directly if obviously relevant.

5. Based on available data, provide your assessment:

### Relevance Assessment
- **Relevant**: Active in earth/environmental/ocean/atmospheric/planetary sciences
- **Possibly relevant**: Some connection but unclear
- **Not relevant**: No apparent connection to earth sciences

### Entity Type
One of: individual, institution, department, society, journal, podcast, service, bot

### Suggested Categories
From: geodynamics, seismology, volcanology, petrology, mineralogy, geochemistry, paleontology, geomorphology, hydrogeology, planetary_science, geophysics, tectonics, sedimentology, glaciology, geodesy, stratigraphy, marine_geology, environmental_science, climate_science, atmospheric_science, oceanography, ecology, sustainability, natural_hazards, remote_sensing, engineering_geology, other

### Recommendation
- Add to list / Keep on list
- Remove from list
- Needs more information (suggest `bsky-geo evaluate <handle>`)

6. If I decide to add them, remind me to run `bsky-geo add <handle>`.
