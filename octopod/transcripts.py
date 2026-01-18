"""YouTube transcript fetching for OctoPod."""

from dataclasses import dataclass

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

from .database import get_videos_without_transcripts, update_video_transcript


@dataclass
class TranscriptResult:
    """Result of a transcript fetch attempt."""
    video_id: str
    success: bool
    transcript: str | None = None
    error: str | None = None


def fetch_transcript(video_id: str) -> TranscriptResult:
    """Fetch transcript for a single video."""
    try:
        api = YouTubeTranscriptApi()

        # Try to fetch transcript directly (will get default/auto-generated)
        transcript_data = api.fetch(video_id)

        # Format the transcript text
        formatted_text = " ".join(
            snippet.text for snippet in transcript_data
        )

        return TranscriptResult(
            video_id=video_id,
            success=True,
            transcript=formatted_text
        )

    except TranscriptsDisabled:
        return TranscriptResult(
            video_id=video_id,
            success=False,
            error="Transcripts are disabled for this video"
        )
    except VideoUnavailable:
        return TranscriptResult(
            video_id=video_id,
            success=False,
            error="Video is unavailable"
        )
    except NoTranscriptFound:
        return TranscriptResult(
            video_id=video_id,
            success=False,
            error="No transcript found"
        )
    except Exception as e:
        return TranscriptResult(
            video_id=video_id,
            success=False,
            error=str(e)
        )


def fetch_and_store_transcripts() -> dict[str, list[TranscriptResult]]:
    """Fetch transcripts for all videos that don't have them yet."""
    videos = get_videos_without_transcripts()
    results: dict[str, list[TranscriptResult]] = {
        "success": [],
        "failed": []
    }

    for video in videos:
        result = fetch_transcript(video["id"])

        if result.success and result.transcript:
            update_video_transcript(video["id"], result.transcript)
            results["success"].append(result)
        else:
            results["failed"].append(result)

    return results
