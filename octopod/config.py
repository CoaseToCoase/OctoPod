"""Configuration and channel mappings for OctoPod."""

import os
from pathlib import Path

# Database configuration
DEFAULT_DB_PATH = Path(__file__).parent.parent / "data" / "octopod.db"
DB_PATH = Path(os.environ.get("OCTOPOD_DB_PATH", DEFAULT_DB_PATH))

# Anthropic API configuration
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = "claude-sonnet-4-20250514"

# YouTube RSS feed URL template
YOUTUBE_RSS_TEMPLATE = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"

# Channel configurations
CHANNELS = {
    "draft_fc": {
        "name": "Draft FC",
        "youtube_channel_id": "UC1fzfDlBWbawMMbwOczk58Q",
    },
    "fpl_draftzone": {
        "name": "FPL Draftzone",
        "youtube_channel_id": "UC1iLU8Nb1Rb-43Ld6zqCgGw",
    },
    "ff_scout": {
        "name": "Fantasy Football Scout",
        "youtube_channel_id": "UCKxYKQ8pgJ7V8wwh4hLsSXQ",
    },
    "fpl_mate": {
        "name": "FPL Mate",
        "youtube_channel_id": "UCweDAlFm2LnVcOqaFU4_AGA",
    },
}


def get_channel_rss_url(channel_id: str) -> str:
    """Get the RSS feed URL for a YouTube channel."""
    return YOUTUBE_RSS_TEMPLATE.format(channel_id=channel_id)
