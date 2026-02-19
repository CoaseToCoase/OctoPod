"""Configuration loader for OctoPod."""

import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"

# API configuration
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# YouTube RSS feed URL template
YOUTUBE_RSS_TEMPLATE = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"

# Current category (replaces "profile" concept)
_current_category: str = "FPL Draft"
_config_cache: dict[str, Any] | None = None


def list_categories() -> list[str]:
    """List all available categories from channels.json."""
    channels_file = CONFIG_DIR / "channels.json"
    if not channels_file.exists():
        return []

    with open(channels_file) as f:
        channels = json.load(f)
    return list(channels.keys())


def set_category(category: str) -> None:
    """Set the current category."""
    global _current_category, _config_cache

    available = list_categories()
    if category not in available and available:
        raise ValueError(
            f"Category '{category}' not found. Available: {', '.join(available)}"
        )

    _current_category = category
    _config_cache = None  # Clear cache when category changes


def get_category() -> str:
    """Get the current category name."""
    return _current_category


def get_category_data_dir() -> Path:
    """Get the data directory for the current category."""
    # Convert category name to filesystem-safe format
    safe_name = _current_category.replace(" ", "_").lower()
    return DATA_DIR / safe_name


def load_all_configs() -> dict[str, Any]:
    """Load all JSON config files."""
    global _config_cache
    if _config_cache is not None:
        return _config_cache

    configs = {}
    config_files = {
        'channels': CONFIG_DIR / 'channels.json',
        'prompts': CONFIG_DIR / 'prompts.json',
        'models': CONFIG_DIR / 'models.json',
        'schedules': CONFIG_DIR / 'schedules.json'
    }

    for name, path in config_files.items():
        if path.exists():
            with open(path) as f:
                configs[name] = json.load(f)
        else:
            configs[name] = {}

    _config_cache = configs
    return _config_cache


def get_channels() -> list[dict[str, str]]:
    """Get channel configurations for current category."""
    configs = load_all_configs()
    channels = configs.get('channels', {}).get(_current_category, [])
    return channels


def get_channels_dict() -> dict[str, dict[str, str]]:
    """Get channels as a dictionary keyed by channel ID."""
    channels = get_channels()
    return {
        ch["id"]: {
            "name": ch["name"],
            "url": ch.get("url", ""),
        }
        for ch in channels
    }


def get_analysis_prompt() -> str:
    """Get the analysis prompt for current category."""
    configs = load_all_configs()
    return configs.get('prompts', {}).get(_current_category, "")


def get_summary_prompt() -> str:
    """Get the summary prompt (uses analysis prompt for now)."""
    # Could add a separate summary_prompts.json later
    return get_analysis_prompt()


def get_model() -> str:
    """Get the AI model to use for current category."""
    configs = load_all_configs()
    return configs.get('models', {}).get(_current_category, "claude-haiku-4-5-20251001")


def get_gcs_config() -> dict[str, str]:
    """Get GCS configuration."""
    # GCS bucket is consistent across categories
    safe_category = _current_category.replace(" ", "_")
    return {
        "bucket": "octosuitedatahub",
        "path_prefix": f"octopod/reports/{safe_category}"
    }


def get_schedule_config() -> dict[str, Any]:
    """Get schedule configuration for current category.

    Returns config like:
        {"type": "gameweek", "value": "24", "description": "..."}
        {"type": "cron", "value": "0 9 * * FRI", "description": "..."}
    """
    configs = load_all_configs()
    return configs.get('schedules', {}).get(_current_category, {"type": "cron", "value": "0 0 * * *"})


def get_channel_rss_url(channel_id: str) -> str:
    """Get the RSS feed URL for a YouTube channel."""
    return YOUTUBE_RSS_TEMPLATE.format(channel_id=channel_id)


# Backward compatibility aliases
def get_profile() -> str:
    """Alias for get_category() for backwards compatibility."""
    return get_category()


def set_profile(profile: str) -> None:
    """Alias for set_category() for backwards compatibility."""
    set_category(profile)


def get_profile_data_dir() -> Path:
    """Alias for get_category_data_dir() for backwards compatibility."""
    return get_category_data_dir()


def list_profiles() -> list[str]:
    """Alias for list_categories() for backwards compatibility."""
    return list_categories()


# For backwards compatibility
CHANNELS = {}  # Will be populated on first access if needed
