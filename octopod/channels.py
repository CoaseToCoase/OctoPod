"""YouTube channel RSS feed handling for OctoPod."""

import ssl
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone

import feedparser
from dateutil import parser as date_parser

from .config import get_channel_rss_url
from .data import get_all_channels, upsert_video


def _create_ssl_context():
    """Create an SSL context that works on systems with certificate issues."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


@dataclass
class VideoEntry:
    """Represents a video entry from an RSS feed."""
    video_id: str
    title: str
    published_at: datetime | None
    channel_id: str


def parse_video_id_from_link(link: str) -> str | None:
    """Extract video ID from a YouTube link."""
    # YouTube RSS links are in format: https://www.youtube.com/watch?v=VIDEO_ID
    if "watch?v=" in link:
        return link.split("watch?v=")[-1].split("&")[0]
    return None


def fetch_channel_videos(youtube_channel_id: str, channel_id: str) -> list[VideoEntry]:
    """Fetch recent videos from a YouTube channel's RSS feed."""
    rss_url = get_channel_rss_url(youtube_channel_id)

    # Fetch with custom SSL context to handle certificate issues
    try:
        ctx = _create_ssl_context()
        with urllib.request.urlopen(rss_url, context=ctx) as response:
            feed_content = response.read()
        feed = feedparser.parse(feed_content)
    except Exception:
        # Fallback to direct parse if urllib fails
        feed = feedparser.parse(rss_url)

    videos = []
    for entry in feed.entries:
        video_id = entry.get("yt_videoid")
        if not video_id:
            # Try to extract from link
            video_id = parse_video_id_from_link(entry.get("link", ""))

        if not video_id:
            continue

        # Parse published date
        published_at = None
        if "published" in entry:
            try:
                published_at = date_parser.parse(entry.published)
            except (ValueError, TypeError):
                pass

        videos.append(VideoEntry(
            video_id=video_id,
            title=entry.get("title", "Unknown Title"),
            published_at=published_at,
            channel_id=channel_id
        ))

    return videos


def fetch_all_channels() -> dict[str, list[VideoEntry]]:
    """Fetch videos from all configured channels."""
    channels = get_all_channels()
    all_videos: dict[str, list[VideoEntry]] = {}

    for channel in channels:
        # Use 'id' as YouTube channel ID (frontend format)
        youtube_id = channel.get("id") or channel.get("youtube_channel_id")
        videos = fetch_channel_videos(
            youtube_id,
            youtube_id  # Use same ID for both
        )
        all_videos[channel["name"]] = videos

    return all_videos


def fetch_and_store_videos(since: datetime | None = None) -> dict[str, int]:
    """Fetch videos from all channels and store them in the database.

    Args:
        since: Only include videos published after this datetime.
               If None, includes all videos from the RSS feed.
    """
    channels = get_all_channels()
    results: dict[str, int] = {}

    for channel in channels:
        # Use 'id' as YouTube channel ID (frontend format)
        youtube_id = channel.get("id") or channel.get("youtube_channel_id")
        videos = fetch_channel_videos(
            youtube_id,
            youtube_id  # Use same ID for both
        )

        # Filter by date if specified
        if since is not None:
            # Ensure since is timezone-aware for comparison
            if since.tzinfo is None:
                since = since.replace(tzinfo=timezone.utc)
            videos = [
                v for v in videos
                if v.published_at is not None and v.published_at >= since
            ]

        for video in videos:
            upsert_video(
                video_id=video.video_id,
                channel_id=video.channel_id,
                title=video.title,
                published_at=video.published_at
            )

        results[channel["name"]] = len(videos)

    return results
