"""Schedule handling for different profile types."""

from datetime import datetime, timedelta, timezone
from typing import Any


def get_schedule_range(schedule_config: dict[str, Any]) -> tuple[datetime | None, str]:
    """Get the date range for fetching/summarizing based on schedule config.

    Args:
        schedule_config: Schedule configuration from profile YAML

    Returns:
        Tuple of (since_datetime, period_label)
        since_datetime is None if we can't determine the range
    """
    schedule_type = schedule_config.get("type", "rolling_days")

    if schedule_type == "fpl_gameweek":
        return _get_fpl_gameweek_range()
    elif schedule_type == "rolling_days":
        days = schedule_config.get("days", 7)
        return _get_rolling_days_range(days)
    elif schedule_type == "weekly":
        start_day = schedule_config.get("start_day", "monday")
        return _get_weekly_range(start_day)
    elif schedule_type == "daily":
        return _get_daily_range()
    else:
        # Default to 7 days
        return _get_rolling_days_range(7)


def get_period_identifier(schedule_config: dict[str, Any]) -> str:
    """Get a string identifier for the current period (for naming summaries).

    Args:
        schedule_config: Schedule configuration from profile YAML

    Returns:
        Period identifier string (e.g., "gw26", "2024-w05", "2024-02-15")
    """
    schedule_type = schedule_config.get("type", "rolling_days")
    now = datetime.now(timezone.utc)

    if schedule_type == "fpl_gameweek":
        from .fpl import get_current_gameweek
        gw = get_current_gameweek()
        if gw:
            return f"gw{gw['id']}"
        return now.strftime("%Y-%m-%d")
    elif schedule_type == "weekly":
        # ISO week number
        return now.strftime("%Y-w%W")
    elif schedule_type == "daily":
        return now.strftime("%Y-%m-%d")
    else:
        # rolling_days - use current date
        return now.strftime("%Y-%m-%d")


def _get_fpl_gameweek_range() -> tuple[datetime | None, str]:
    """Get date range based on FPL gameweek deadlines."""
    from .fpl import get_previous_gameweek_deadline, get_current_gameweek

    since = get_previous_gameweek_deadline()
    gw = get_current_gameweek()

    if gw:
        label = f"GW{gw['id']}"
    else:
        label = "current gameweek"

    return since, label


def _get_rolling_days_range(days: int) -> tuple[datetime, str]:
    """Get date range for rolling N days."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    label = f"last {days} days"
    return since, label


def _get_weekly_range(start_day: str) -> tuple[datetime, str]:
    """Get date range for the current week starting on specified day."""
    day_map = {
        "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
        "friday": 4, "saturday": 5, "sunday": 6
    }

    target_weekday = day_map.get(start_day.lower(), 0)
    now = datetime.now(timezone.utc)

    # Find the most recent occurrence of start_day
    days_since_start = (now.weekday() - target_weekday) % 7
    if days_since_start == 0 and now.hour < 6:  # Before 6am, use previous week
        days_since_start = 7

    since = now - timedelta(days=days_since_start)
    since = since.replace(hour=0, minute=0, second=0, microsecond=0)

    week_num = since.strftime("%W")
    label = f"week {week_num}"

    return since, label


def _get_daily_range() -> tuple[datetime, str]:
    """Get date range for today (since midnight UTC)."""
    now = datetime.now(timezone.utc)
    since = now.replace(hour=0, minute=0, second=0, microsecond=0)
    label = now.strftime("%Y-%m-%d")
    return since, label
