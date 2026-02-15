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
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"

# Anthropic API configuration
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = "claude-sonnet-4-20250514"

# YouTube RSS feed URL template
YOUTUBE_RSS_TEMPLATE = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"

# Current profile (can be set via set_profile())
_current_profile: str = "draft-fpl"
_config_cache: dict[str, Any] | None = None


def list_profiles() -> list[str]:
    """List all available profile names."""
    if not CONFIG_DIR.exists():
        return []
    return [f.stem for f in CONFIG_DIR.glob("*.yaml")]


def set_profile(profile: str) -> None:
    """Set the current profile."""
    global _current_profile, _config_cache

    config_path = CONFIG_DIR / f"{profile}.yaml"
    if not config_path.exists():
        available = list_profiles()
        raise FileNotFoundError(
            f"Profile '{profile}' not found. Available: {', '.join(available)}"
        )

    _current_profile = profile
    _config_cache = None  # Clear cache when profile changes


def get_profile() -> str:
    """Get the current profile name."""
    return _current_profile


def get_profile_data_dir() -> Path:
    """Get the data directory for the current profile."""
    return DATA_DIR / _current_profile


def load_config() -> dict[str, Any]:
    """Load configuration for the current profile."""
    global _config_cache
    if _config_cache is not None:
        return _config_cache

    config_path = CONFIG_DIR / f"{_current_profile}.yaml"

    if not config_path.exists():
        # Fallback to old config.yaml location for backwards compatibility
        old_config = PROJECT_ROOT / "config.yaml"
        if old_config.exists():
            config_path = old_config
        else:
            raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path) as f:
        _config_cache = yaml.safe_load(f)

    return _config_cache


def get_channels() -> list[dict[str, str]]:
    """Get channel configurations from config."""
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
    """Get the analysis prompt from config."""
    config = load_config()
    return config.get("analysis_prompt", "")


def get_summary_prompt() -> str:
    """Get the summary prompt from config."""
    config = load_config()
    return config.get("summary_prompt", "")


def get_gcs_config() -> dict[str, str]:
    """Get GCS configuration from config."""
    config = load_config()
    return config.get("gcs", {"bucket": "", "path_prefix": ""})


def get_schedule_config() -> dict[str, Any]:
    """Get schedule configuration from config.

    Returns config like:
        {"type": "fpl_gameweek"}
        {"type": "rolling_days", "days": 7}
        {"type": "weekly", "start_day": "monday"}
        {"type": "daily"}
    """
    config = load_config()
    return config.get("schedule", {"type": "rolling_days", "days": 7})


def get_channel_rss_url(channel_id: str) -> str:
    """Get the RSS feed URL for a YouTube channel."""
    return YOUTUBE_RSS_TEMPLATE.format(channel_id=channel_id)


# For backwards compatibility
CHANNELS = {}  # Will be populated on first access if needed
