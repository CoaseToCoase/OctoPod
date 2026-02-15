"""Weekly summary generation for OctoPod."""

import json
from datetime import datetime

import anthropic

from .config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL, get_summary_prompt
from .data import get_recent_analyses, get_gameweek_analyses, save_weekly_summary
from .fpl import get_previous_gameweek_deadline, get_current_gameweek_deadline
from .gcs import upload_summary_to_gcs, is_gcs_configured


def generate_weekly_summary(gameweek: int, since: datetime | None = None) -> str | None:
    """Generate a weekly summary from analyses since the previous gameweek deadline.

    Args:
        gameweek: The current gameweek number
        since: Start date for analyses (defaults to previous GW deadline)
    """
    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")

    # Use gameweek deadline if not specified
    if since is None:
        since = get_previous_gameweek_deadline()

    # Get analyses for this gameweek period
    if since:
        analyses = get_gameweek_analyses(since=since)
    else:
        # Fallback to 7 days if we can't get deadline
        analyses = get_recent_analyses(days=7)

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

    # Get prompt from config
    prompt_template = get_summary_prompt()
    prompt = prompt_template.format(
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

    # Get video IDs for storage
    video_ids = [a["video_id"] for a in analyses]

    # Save the summary locally
    save_weekly_summary(gameweek, summary, video_ids)

    # Upload to GCS if configured
    if is_gcs_configured():
        upload_summary_to_gcs(gameweek, summary, video_ids)

    return summary


def get_analysis_stats(since: datetime | None = None) -> dict:
    """Get statistics about analyses since the previous gameweek deadline."""
    # Use gameweek deadline if not specified
    if since is None:
        since = get_previous_gameweek_deadline()

    if since:
        analyses = get_gameweek_analyses(since=since)
    else:
        analyses = get_recent_analyses(days=7)

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
