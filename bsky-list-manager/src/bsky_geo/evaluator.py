"""Claude API evaluation of Bluesky accounts for earth science relevance."""

from __future__ import annotations

import json

import anthropic

EVALUATION_PROMPT = """\
You are helping curate a Bluesky list of earth scientists and related \
researchers, institutions, and organisations. The list feeds a community feed \
covering a broad scope: geology, geophysics, climate science, oceanography, \
atmospheric science, ecology, environmental science, planetary science, \
hydrology, natural hazards, sustainability science, and related disciplines.

Evaluate this account and respond in JSON:

Profile:
- Handle: {handle}
- Display name: {display_name}
- Bio: {bio}
- Follower count: {followers}
- Following count: {following}

Recent posts (last {post_count}):
{posts_text}

Respond with JSON only (no markdown fences):
{{
  "is_relevant": true/false,
  "confidence": 0.0-1.0,
  "entity_type": "individual|institution|department|society|journal",
  "categories": ["list", "of", "subdisciplines"],
  "institution_affiliation": "if detectable",
  "reasoning": "brief explanation",
  "activity_assessment": "active_researcher|occasional_poster|mostly_reposts|inactive|non_science"
}}

Criteria — who belongs on this list:
- Researchers (any career stage) actively working in earth, environmental, \
ocean, atmospheric, or planetary sciences: YES
- Geoscience departments, geological surveys, environmental agencies, \
research institutes: YES
- Relevant academic societies, journals, and science publishers \
(e.g. Nature earth/environment titles, AGU, EGU, GSA journals): YES
- Science communicators with genuine expertise in these fields: YES
- Climate scientists, ecologists, hydrologists, sustainability researchers \
whose work connects to earth systems: YES
- Earthquake/volcano/weather monitoring services and natural hazard agencies: YES

Who does NOT belong:
- Casual science enthusiasts with no professional or research connection: NO
- Accounts that rarely post about earth/environmental science: NO
- Pure policy/advocacy accounts with no scientific content: NO
- Dormant accounts (no posts in 3+ months): FLAG as low confidence

Common false positives to watch for:
- Rock music enthusiasts ("you rock", rock bands, concert posts)
- Rock climbing / bouldering accounts
- Crystal/mineral healing, gemstone jewelry sellers
- Mining industry / cryptocurrency mining
- Landscape photography without scientific context
- General "science fan" accounts with no earth/environmental science focus
- Pure biology/biomedical accounts with no environmental or ecological focus

Subdiscipline categories to choose from:
geodynamics, seismology, volcanology, petrology, mineralogy, geochemistry, \
paleontology, geomorphology, hydrogeology, planetary_science, geophysics, \
tectonics, sedimentology, glaciology, geodesy, stratigraphy, marine_geology, \
environmental_science, climate_science, atmospheric_science, oceanography, \
ecology, sustainability, natural_hazards, remote_sensing, engineering_geology, \
other
"""

CLASSIFICATION_PROMPT = """\
Classify each Bluesky account by entity type and whether it is a bot/automated account.

Entity types:
- individual: a person (researcher, student, professor, science communicator)
- institution: university, research institute, lab, government agency, geological survey
- department: a university department or research group
- society: professional or academic society (AGU, EGU, GSA, etc.)
- journal: academic journal, publisher, or publication account
- podcast: science podcast or media show
- service: monitoring service, data service, alert system (earthquake alerts, weather services)
- bot: automated repost account, RSS bridge, hashtag spammer with no original content

Bot detection — flag is_bot=true for:
- Automated earthquake/weather/natural-hazard alert feeds (e.g. @lastquake)
- Accounts that only repost links with hashtag spam
- RSS-to-social bridges with no original commentary
- Accounts with no original content, only automated reposts
Note: institutional accounts that post curated content are NOT bots.

Accounts to classify:
{accounts_json}

Respond with a JSON array only (no markdown fences). One object per account, in the \
same order as the input:
[
  {{
    "handle": "the handle",
    "entity_type": "individual|institution|department|society|journal|podcast|service|bot",
    "is_bot": true/false,
    "confidence": 0.0-1.0
  }},
  ...
]
"""

MODEL = "claude-sonnet-4-5-20250929"


def classify_batch(
    profiles: list[dict],
    api_key: str | None = None,
) -> list[dict]:
    """Classify a batch of profiles by entity type and bot status.

    Args:
        profiles: List of dicts with handle, display_name, bio (up to 20).
        api_key: Anthropic API key. If None, uses ANTHROPIC_API_KEY env var.

    Returns:
        List of dicts with handle, entity_type, is_bot, confidence.
    """
    accounts = []
    for p in profiles:
        accounts.append({
            "handle": p.get("handle", ""),
            "display_name": p.get("display_name", ""),
            "bio": p.get("description", p.get("bio", "")),
        })

    prompt = CLASSIFICATION_PROMPT.format(accounts_json=json.dumps(accounts, indent=2))

    kwargs = {}
    if api_key:
        kwargs["api_key"] = api_key
    client = anthropic.Anthropic(**kwargs)

    message = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )

    response_text = message.content[0].text.strip()

    # Strip markdown code fences if present
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        response_text = "\n".join(lines)

    try:
        results = json.loads(response_text)
    except json.JSONDecodeError:
        # Return unknowns for all profiles
        results = [
            {
                "handle": p.get("handle", ""),
                "entity_type": "unknown",
                "is_bot": False,
                "confidence": 0.0,
            }
            for p in profiles
        ]

    return results


def evaluate_account(
    profile: dict,
    posts: list[str],
    api_key: str | None = None,
) -> dict:
    """Evaluate a Bluesky account for earth science relevance using Claude.

    Args:
        profile: Dict with handle, display_name, description, followers_count, follows_count.
        posts: List of recent post texts.
        api_key: Anthropic API key. If None, uses ANTHROPIC_API_KEY env var.

    Returns:
        Parsed evaluation dict with is_relevant, confidence, entity_type,
        categories, institution_affiliation, reasoning, activity_assessment.
    """
    posts_text = "\n---\n".join(posts[:50]) if posts else "(no recent posts)"

    prompt = EVALUATION_PROMPT.format(
        handle=profile.get("handle", ""),
        display_name=profile.get("display_name", ""),
        bio=profile.get("description", ""),
        followers=profile.get("followers_count", 0),
        following=profile.get("follows_count", 0),
        post_count=len(posts[:50]),
        posts_text=posts_text,
    )

    kwargs = {}
    if api_key:
        kwargs["api_key"] = api_key
    client = anthropic.Anthropic(**kwargs)

    message = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    response_text = message.content[0].text.strip()

    # Strip markdown code fences if present
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        # Remove first and last lines (``` markers)
        lines = [l for l in lines if not l.strip().startswith("```")]
        response_text = "\n".join(lines)

    try:
        result = json.loads(response_text)
    except json.JSONDecodeError:
        result = {
            "is_relevant": False,
            "confidence": 0.0,
            "entity_type": "unknown",
            "categories": [],
            "institution_affiliation": "",
            "reasoning": f"Failed to parse AI response: {response_text[:200]}",
            "activity_assessment": "unknown",
            "raw_response": response_text,
        }

    return result
