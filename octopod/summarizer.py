"""Weekly summary generation for OctoPod."""

import json

import anthropic

from .config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL
from .database import get_recent_analyses, save_weekly_summary


SUMMARY_PROMPT = """You are an expert Fantasy Premier League (FPL) Draft analyst creating a weekly gameweek summary.

I have collected analysis from multiple FPL podcasts. Your job is to synthesize this information into a coherent, actionable gameweek summary for FPL Draft managers.

The summary should include:

1. **Consensus Picks**: Players that multiple sources agree on (either to buy or avoid)
2. **Hot Topics**: The most discussed players this week and what's being said
3. **Injury Updates**: Key injury news and return timelines
4. **Waiver Wire Targets**: Recommended pickups for Draft managers
5. **Players to Sell/Drop**: Players that sources recommend moving on from
6. **Differential Picks**: Under-the-radar options that could pay off
7. **Captain Recommendations**: Top captaincy options for the gameweek
8. **Differing Opinions**: Where pundits disagree (note both sides)

Format the summary in clear markdown with headers and bullet points.
Be specific with player names and include context for each recommendation.
Highlight when multiple sources agree on something.
Note which channel/source made each recommendation when relevant.

Here is the analysis data from {num_videos} videos across {num_channels} channels:

{analysis_data}

Create a comprehensive Gameweek {gameweek} summary:"""


def generate_weekly_summary(gameweek: int, days: int = 7) -> str | None:
    """Generate a weekly summary from recent analyses."""
    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")

    analyses = get_recent_analyses(days=days)

    if not analyses:
        return None

    # Prepare the analysis data for the prompt
    channels_seen = set()
    analysis_entries = []

    for analysis in analyses:
        channels_seen.add(analysis["channel_name"])

        entry = {
            "source": analysis["channel_name"],
            "video_title": analysis["title"],
            "published": str(analysis["published_at"]),
            "player_mentions": analysis["player_mentions"],
            "recommendations": analysis["recommendations"],
            "injury_news": analysis["injury_news"],
        }
        analysis_entries.append(entry)

    analysis_data = json.dumps(analysis_entries, indent=2)

    prompt = SUMMARY_PROMPT.format(
        num_videos=len(analyses),
        num_channels=len(channels_seen),
        analysis_data=analysis_data,
        gameweek=gameweek
    )

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    message = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=4096,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    summary = message.content[0].text

    # Save the summary
    video_ids = [a["video_id"] for a in analyses]
    save_weekly_summary(gameweek, summary, video_ids)

    return summary


def get_analysis_stats(days: int = 7) -> dict:
    """Get statistics about recent analyses."""
    analyses = get_recent_analyses(days=days)

    if not analyses:
        return {
            "total_videos": 0,
            "channels": [],
            "player_mention_count": 0,
            "recommendation_count": 0
        }

    channels = set()
    total_mentions = 0
    total_recommendations = 0

    for analysis in analyses:
        channels.add(analysis["channel_name"])
        total_mentions += len(analysis["player_mentions"])
        total_recommendations += len(analysis["recommendations"])

    return {
        "total_videos": len(analyses),
        "channels": list(channels),
        "player_mention_count": total_mentions,
        "recommendation_count": total_recommendations
    }
