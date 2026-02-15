"""Summary generation for OctoPod."""

import json
from datetime import datetime
from dataclasses import dataclass

import anthropic

from .config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL, get_summary_prompt, get_schedule_config
from .data import get_recent_analyses, get_gameweek_analyses, save_summary
from .schedule import get_schedule_range, get_period_identifier
from .gcs import upload_summary_to_gcs, is_gcs_configured


# Haiku 3.5 pricing per million tokens
INPUT_COST_PER_M = 0.80
OUTPUT_COST_PER_M = 4.0


@dataclass
class SummaryUsage:
    """Token usage for summary generation."""
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0


def generate_summary(period: str | None = None, since: datetime | None = None) -> tuple[str | None, SummaryUsage]:
    """Generate a summary from analyses for the specified period.

    Args:
        period: Period identifier (e.g., "gw26", "2024-w05"). Auto-detected if not provided.
        since: Start date for analyses. Uses schedule config if not provided.

    Returns:
        Tuple of (summary_text, usage_info)
    """
    usage = SummaryUsage()

    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")

    schedule_config = get_schedule_config()

    # Use schedule config if since not specified
    if since is None:
        since, _ = get_schedule_range(schedule_config)

    # Auto-detect period if not provided
    if period is None:
        period = get_period_identifier(schedule_config)

    # Get analyses for this period
    if since:
        analyses = get_gameweek_analyses(since=since)
    else:
        # Fallback to 7 days
        analyses = get_recent_analyses(days=7)

    if not analyses:
        return None, usage

    # Prepare the analysis data for the prompt
    channels_seen = set()
    analysis_entries = []

    for analysis in analyses:
        channels_seen.add(analysis["channel_name"])

        entry = {
            "source": analysis["channel_name"],
            "video_title": analysis["title"],
            "published": str(analysis["published_at"]),
            "player_mentions": analysis.get("player_mentions", []),
            "recommendations": analysis.get("recommendations", []),
            "injury_news": analysis.get("injury_news", []),
        }
        analysis_entries.append(entry)

    analysis_data = json.dumps(analysis_entries, indent=2)

    # Get prompt from config
    prompt_template = get_summary_prompt()

    # Support both {gameweek} and {period} placeholders for backwards compatibility
    prompt = prompt_template.format(
        num_videos=len(analyses),
        num_channels=len(channels_seen),
        analysis_data=analysis_data,
        gameweek=period,  # backwards compatibility
        period=period
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
    usage.input_tokens = message.usage.input_tokens
    usage.output_tokens = message.usage.output_tokens
    usage.cost = (usage.input_tokens * INPUT_COST_PER_M / 1_000_000) + (usage.output_tokens * OUTPUT_COST_PER_M / 1_000_000)

    # Get video IDs for storage
    video_ids = [a["video_id"] for a in analyses]

    # Save the summary locally
    save_summary(period, summary, video_ids)

    # Upload to GCS if configured
    if is_gcs_configured():
        upload_summary_to_gcs(period, summary, video_ids)

    return summary, usage


def get_analysis_stats(since: datetime | None = None) -> dict:
    """Get statistics about analyses for the specified period.

    Args:
        since: Start date for analyses. Uses schedule config if not provided.
    """
    # Use schedule config if not specified
    if since is None:
        schedule_config = get_schedule_config()
        since, _ = get_schedule_range(schedule_config)

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
        total_mentions += len(analysis.get("player_mentions", []))
        total_recommendations += len(analysis.get("recommendations", []))

    return {
        "total_videos": len(analyses),
        "channels": list(channels),
        "player_mention_count": total_mentions,
        "recommendation_count": total_recommendations
    }
