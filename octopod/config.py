"""Configuration loader for OctoPod."""

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.yaml"
DATA_DIR = PROJECT_ROOT / "data"

# Anthropic API configuration
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = "claude-sonnet-4-20250514"

# YouTube RSS feed URL template
YOUTUBE_RSS_TEMPLATE = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"

# Cache for loaded config
_config_cache: dict[str, Any] | None = None


def load_config() -> dict[str, Any]:
    """Load configuration from YAML file."""
    global _config_cache
    if _config_cache is not None:
        return _config_cache

    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Config file not found: {CONFIG_PATH}")

    with open(CONFIG_PATH) as f:
        _config_cache = yaml.safe_load(f)

    return _config_cache


def get_channels() -> list[dict[str, str]]:
    """Get channel configurations from config.yaml."""
    config = load_config()
    return config.get("channels", [])


def get_channels_dict() -> dict[str, dict[str, str]]:
    """Get channels as a dictionary keyed by channel ID."""
    channels = get_channels()
    return {
        ch["id"]: {
            "name": ch["name"],
            "youtube_channel_id": ch["youtube_channel_id"],
        }
        for ch in channels
    }


def get_analysis_prompt() -> str:
    """Get the analysis prompt from config.yaml."""
    config = load_config()
    return config.get("analysis_prompt", "")


def get_summary_prompt() -> str:
    """Get the summary prompt from config.yaml."""
    config = load_config()
    return config.get("summary_prompt", "")


def get_gcs_config() -> dict[str, str]:
    """Get GCS configuration from config.yaml."""
    config = load_config()
    return config.get("gcs", {"bucket": "", "path_prefix": ""})


def get_channel_rss_url(channel_id: str) -> str:
    """Get the RSS feed URL for a YouTube channel."""
    return YOUTUBE_RSS_TEMPLATE.format(channel_id=channel_id)


# For backwards compatibility with existing code
CHANNELS = get_channels_dict()
