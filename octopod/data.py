"""JSON file-based data operations for OctoPod."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .config import get_profile_data_dir, get_channels


def _get_videos_file() -> Path:
    """Get the videos.json path for the current profile."""
    return get_profile_data_dir() / "videos.json"


def _get_analyses_file() -> Path:
    """Get the analyses.json path for the current profile."""
    return get_profile_data_dir() / "analyses.json"


def _get_summaries_dir() -> Path:
    """Get the summaries directory path for the current profile."""
    return get_profile_data_dir() / "summaries"


def _ensure_data_dir() -> None:
    """Ensure the data directory structure exists for the current profile."""
    profile_dir = get_profile_data_dir()
    profile_dir.mkdir(parents=True, exist_ok=True)
    _get_summaries_dir().mkdir(parents=True, exist_ok=True)


def _load_json(path: Path) -> dict[str, Any]:
    """Load JSON file, returning empty dict if file doesn't exist."""
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


def _save_json(path: Path, data: dict[str, Any]) -> None:
    """Save data to JSON file with pretty formatting."""
    _ensure_data_dir()
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)


def _datetime_to_str(dt: datetime | None) -> str | None:
    """Convert datetime to ISO format string."""
    if dt is None:
        return None
    return dt.isoformat()


def _str_to_datetime(s: str | None) -> datetime | None:
    """Convert ISO format string to datetime."""
    if s is None:
        return None
    return datetime.fromisoformat(s)


def init_db() -> None:
    """Initialize the data files (creates directories and empty files if needed)."""
    _ensure_data_dir()

    videos_file = _get_videos_file()
    analyses_file = _get_analyses_file()

    # Initialize videos.json if it doesn't exist
    if not videos_file.exists():
        _save_json(videos_file, {})

    # Initialize analyses.json if it doesn't exist
    if not analyses_file.exists():
        _save_json(analyses_file, {})


def get_all_channels() -> list[dict[str, Any]]:
    """Get all channels from the config."""
    return get_channels()


def add_channel(channel_id: str, name: str, youtube_channel_id: str) -> None:
    """Add a new channel - note: channels are now managed in config.yaml."""
    raise NotImplementedError(
        "Channels are now managed in config.yaml. Edit that file to add channels."
    )


def get_channel_by_youtube_id(youtube_channel_id: str) -> dict[str, Any] | None:
    """Get a channel by its YouTube channel ID."""
    channels = get_channels()
    for ch in channels:
        if ch["youtube_channel_id"] == youtube_channel_id:
            return ch
    return None


def upsert_video(
    video_id: str,
    channel_id: str,
    title: str,
    published_at: datetime | None = None
) -> None:
    """Insert or update a video record."""
    videos_file = _get_videos_file()
    videos = _load_json(videos_file)

    videos[video_id] = {
        "id": video_id,
        "channel_id": channel_id,
        "title": title,
        "published_at": _datetime_to_str(published_at),
        "transcript": videos.get(video_id, {}).get("transcript"),
        "transcript_fetched_at": videos.get(video_id, {}).get("transcript_fetched_at"),
    }

    _save_json(videos_file, videos)


def get_videos_without_transcripts() -> list[dict[str, Any]]:
    """Get videos that don't have transcripts yet."""
    videos = _load_json(_get_videos_file())
    channels = {ch["id"]: ch["name"] for ch in get_channels()}

    result = []
    for video_id, video in videos.items():
        if video.get("transcript") is None:
            video_data = {
                **video,
                "channel_name": channels.get(video["channel_id"], "Unknown"),
                "published_at": _str_to_datetime(video.get("published_at")),
            }
            result.append(video_data)

    # Sort by published_at descending
    result.sort(
        key=lambda v: v.get("published_at") or datetime.min,
        reverse=True
    )
    return result


def update_video_transcript(video_id: str, transcript: str) -> None:
    """Update a video's transcript."""
    videos_file = _get_videos_file()
    videos = _load_json(videos_file)

    if video_id in videos:
        videos[video_id]["transcript"] = transcript
        videos[video_id]["transcript_fetched_at"] = _datetime_to_str(datetime.now())
        _save_json(videos_file, videos)


def get_videos_without_analysis() -> list[dict[str, Any]]:
    """Get videos with transcripts that haven't been analyzed yet."""
    videos = _load_json(_get_videos_file())
    analyses = _load_json(_get_analyses_file())
    channels = {ch["id"]: ch["name"] for ch in get_channels()}

    result = []
    for video_id, video in videos.items():
        if video.get("transcript") is not None and video_id not in analyses:
            video_data = {
                **video,
                "id": video_id,
                "channel_name": channels.get(video["channel_id"], "Unknown"),
                "published_at": _str_to_datetime(video.get("published_at")),
            }
            result.append(video_data)

    # Sort by published_at descending
    result.sort(
        key=lambda v: v.get("published_at") or datetime.min,
        reverse=True
    )
    return result


def save_analysis(
    video_id: str,
    player_mentions: list[dict],
    recommendations: list[dict],
    injury_news: list[dict],
    raw_analysis: str
) -> None:
    """Save analysis results for a video."""
    analyses_file = _get_analyses_file()
    analyses = _load_json(analyses_file)

    analyses[video_id] = {
        "video_id": video_id,
        "analyzed_at": _datetime_to_str(datetime.now()),
        "player_mentions": player_mentions,
        "recommendations": recommendations,
        "injury_news": injury_news,
        "raw_analysis": raw_analysis,
    }

    _save_json(analyses_file, analyses)


def get_analysis_for_video(video_id: str) -> dict[str, Any] | None:
    """Get analysis results for a specific video."""
    analyses = _load_json(_get_analyses_file())
    return analyses.get(video_id)


def get_recent_analyses(days: int = 7) -> list[dict[str, Any]]:
    """Get analyses from the past N days."""
    from datetime import timezone

    videos = _load_json(_get_videos_file())
    analyses = _load_json(_get_analyses_file())
    channels = {ch["id"]: ch["name"] for ch in get_channels()}

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    results = []

    for video_id, analysis in analyses.items():
        video = videos.get(video_id, {})
        published_at = _str_to_datetime(video.get("published_at"))

        if published_at and published_at >= cutoff:
            result = {
                **analysis,
                "title": video.get("title", "Unknown"),
                "published_at": published_at,
                "channel_name": channels.get(video.get("channel_id", ""), "Unknown"),
            }
            results.append(result)

    # Sort by published_at descending
    results.sort(
        key=lambda r: r.get("published_at") or datetime.min,
        reverse=True
    )
    return results


def get_gameweek_analyses(since: datetime, until: datetime | None = None) -> list[dict[str, Any]]:
    """Get analyses for videos published between gameweek deadlines."""
    from datetime import timezone

    videos = _load_json(_get_videos_file())
    analyses = _load_json(_get_analyses_file())
    channels = {ch["id"]: ch["name"] for ch in get_channels()}

    # Ensure timezone aware
    if since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)
    if until is None:
        until = datetime.now(timezone.utc)
    elif until.tzinfo is None:
        until = until.replace(tzinfo=timezone.utc)

    results = []

    for video_id, analysis in analyses.items():
        video = videos.get(video_id, {})
        published_at = _str_to_datetime(video.get("published_at"))

        if published_at and since <= published_at <= until:
            result = {
                **analysis,
                "title": video.get("title", "Unknown"),
                "published_at": published_at,
                "channel_name": channels.get(video.get("channel_id", ""), "Unknown"),
            }
            results.append(result)

    # Sort by published_at descending
    results.sort(
        key=lambda r: r.get("published_at") or datetime.min,
        reverse=True
    )
    return results


def save_summary(
    period: str,
    summary: str,
    video_ids: list[str]
) -> None:
    """Save a period summary."""
    summaries_dir = _get_summaries_dir()
    summaries_dir.mkdir(parents=True, exist_ok=True)
    summary_file = summaries_dir / f"{period}.json"

    summary_data = {
        "period": period,
        "created_at": _datetime_to_str(datetime.now()),
        "summary": summary,
        "videos_included": video_ids,
    }

    _save_json(summary_file, summary_data)


def get_summary(period: str) -> dict[str, Any] | None:
    """Get a summary by period identifier."""
    summary_file = _get_summaries_dir() / f"{period}.json"

    if not summary_file.exists():
        return None

    return _load_json(summary_file)


# Backwards compatibility aliases
def save_weekly_summary(gameweek: int, summary: str, video_ids: list[str]) -> None:
    """Deprecated: Use save_summary instead."""
    save_summary(f"gw{gameweek}", summary, video_ids)


def get_weekly_summary(gameweek: int) -> dict[str, Any] | None:
    """Deprecated: Use get_summary instead."""
    return get_summary(f"gw{gameweek}")


def get_all_videos(limit: int = 50) -> list[dict[str, Any]]:
    """Get all videos ordered by publish date."""
    videos = _load_json(_get_videos_file())
    analyses = _load_json(_get_analyses_file())
    channels = {ch["id"]: ch["name"] for ch in get_channels()}

    result = []
    for video_id, video in videos.items():
        video_data = {
            **video,
            "id": video_id,
            "channel_name": channels.get(video["channel_id"], "Unknown"),
            "published_at": _str_to_datetime(video.get("published_at")),
            "has_analysis": video_id in analyses,
        }
        result.append(video_data)

    # Sort by published_at descending
    result.sort(
        key=lambda v: v.get("published_at") or datetime.min,
        reverse=True
    )

    return result[:limit]
