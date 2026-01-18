"""SQLite database operations for OctoPod."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Any

from .config import DB_PATH, CHANNELS


def get_connection() -> sqlite3.Connection:
    """Get a database connection."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def get_db():
    """Context manager for database connections."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """Initialize the database schema."""
    with get_db() as conn:
        cursor = conn.cursor()

        # Channels table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS channels (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                youtube_channel_id TEXT NOT NULL UNIQUE
            )
        """)

        # Videos table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                id TEXT PRIMARY KEY,
                channel_id TEXT NOT NULL,
                title TEXT NOT NULL,
                published_at DATETIME,
                transcript TEXT,
                transcript_fetched_at DATETIME,
                FOREIGN KEY (channel_id) REFERENCES channels(id)
            )
        """)

        # Analysis results table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analysis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id TEXT NOT NULL UNIQUE,
                analyzed_at DATETIME,
                player_mentions TEXT,
                recommendations TEXT,
                injury_news TEXT,
                raw_analysis TEXT,
                FOREIGN KEY (video_id) REFERENCES videos(id)
            )
        """)

        # Weekly summaries table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS weekly_summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                gameweek INTEGER NOT NULL,
                created_at DATETIME,
                summary TEXT NOT NULL,
                videos_included TEXT
            )
        """)

        # Create indexes for common queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_videos_channel_id ON videos(channel_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_videos_published_at ON videos(published_at)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_analysis_video_id ON analysis(video_id)
        """)

        # Seed default channels
        for channel_id, channel_info in CHANNELS.items():
            cursor.execute("""
                INSERT OR IGNORE INTO channels (id, name, youtube_channel_id)
                VALUES (?, ?, ?)
            """, (channel_id, channel_info["name"], channel_info["youtube_channel_id"]))


def get_all_channels() -> list[dict[str, Any]]:
    """Get all channels from the database."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM channels")
        return [dict(row) for row in cursor.fetchall()]


def add_channel(channel_id: str, name: str, youtube_channel_id: str) -> None:
    """Add a new channel to the database."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO channels (id, name, youtube_channel_id)
            VALUES (?, ?, ?)
        """, (channel_id, name, youtube_channel_id))


def get_channel_by_youtube_id(youtube_channel_id: str) -> dict[str, Any] | None:
    """Get a channel by its YouTube channel ID."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM channels WHERE youtube_channel_id = ?",
            (youtube_channel_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def upsert_video(
    video_id: str,
    channel_id: str,
    title: str,
    published_at: datetime | None = None
) -> None:
    """Insert or update a video record."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO videos (id, channel_id, title, published_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title,
                published_at = excluded.published_at
        """, (video_id, channel_id, title, published_at))


def get_videos_without_transcripts() -> list[dict[str, Any]]:
    """Get videos that don't have transcripts yet."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT v.*, c.name as channel_name
            FROM videos v
            JOIN channels c ON v.channel_id = c.id
            WHERE v.transcript IS NULL
            ORDER BY v.published_at DESC
        """)
        return [dict(row) for row in cursor.fetchall()]


def update_video_transcript(video_id: str, transcript: str) -> None:
    """Update a video's transcript."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE videos
            SET transcript = ?, transcript_fetched_at = ?
            WHERE id = ?
        """, (transcript, datetime.now(), video_id))


def get_videos_without_analysis() -> list[dict[str, Any]]:
    """Get videos with transcripts that haven't been analyzed yet."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT v.*, c.name as channel_name
            FROM videos v
            JOIN channels c ON v.channel_id = c.id
            LEFT JOIN analysis a ON v.id = a.video_id
            WHERE v.transcript IS NOT NULL AND a.id IS NULL
            ORDER BY v.published_at DESC
        """)
        return [dict(row) for row in cursor.fetchall()]


def save_analysis(
    video_id: str,
    player_mentions: list[dict],
    recommendations: list[dict],
    injury_news: list[dict],
    raw_analysis: str
) -> None:
    """Save analysis results for a video."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO analysis (
                video_id, analyzed_at, player_mentions,
                recommendations, injury_news, raw_analysis
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            video_id,
            datetime.now(),
            json.dumps(player_mentions),
            json.dumps(recommendations),
            json.dumps(injury_news),
            raw_analysis
        ))


def get_analysis_for_video(video_id: str) -> dict[str, Any] | None:
    """Get analysis results for a specific video."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM analysis WHERE video_id = ?", (video_id,))
        row = cursor.fetchone()
        if row:
            result = dict(row)
            result["player_mentions"] = json.loads(result["player_mentions"] or "[]")
            result["recommendations"] = json.loads(result["recommendations"] or "[]")
            result["injury_news"] = json.loads(result["injury_news"] or "[]")
            return result
        return None


def get_recent_analyses(days: int = 7) -> list[dict[str, Any]]:
    """Get analyses from the past N days."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT a.*, v.title, v.published_at, c.name as channel_name
            FROM analysis a
            JOIN videos v ON a.video_id = v.id
            JOIN channels c ON v.channel_id = c.id
            WHERE v.published_at >= datetime('now', ?)
            ORDER BY v.published_at DESC
        """, (f"-{days} days",))
        results = []
        for row in cursor.fetchall():
            result = dict(row)
            result["player_mentions"] = json.loads(result["player_mentions"] or "[]")
            result["recommendations"] = json.loads(result["recommendations"] or "[]")
            result["injury_news"] = json.loads(result["injury_news"] or "[]")
            results.append(result)
        return results


def save_weekly_summary(
    gameweek: int,
    summary: str,
    video_ids: list[str]
) -> None:
    """Save a weekly summary."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO weekly_summaries (gameweek, created_at, summary, videos_included)
            VALUES (?, ?, ?, ?)
        """, (gameweek, datetime.now(), summary, json.dumps(video_ids)))


def get_weekly_summary(gameweek: int) -> dict[str, Any] | None:
    """Get a weekly summary by gameweek number."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM weekly_summaries WHERE gameweek = ? ORDER BY created_at DESC LIMIT 1",
            (gameweek,)
        )
        row = cursor.fetchone()
        if row:
            result = dict(row)
            result["videos_included"] = json.loads(result["videos_included"] or "[]")
            return result
        return None


def get_all_videos(limit: int = 50) -> list[dict[str, Any]]:
    """Get all videos ordered by publish date."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT v.*, c.name as channel_name,
                   CASE WHEN a.id IS NOT NULL THEN 1 ELSE 0 END as has_analysis
            FROM videos v
            JOIN channels c ON v.channel_id = c.id
            LEFT JOIN analysis a ON v.id = a.video_id
            ORDER BY v.published_at DESC
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]
