"""YouTube transcript fetching for OctoPod."""

import os
import requests
from dataclasses import dataclass

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

from .data import get_videos_without_transcripts, update_video_transcript

# Cloud Function URL for fetching transcripts (bypasses IP blocking)
CLOUD_FUNCTION_URL = "https://us-central1-octopod-b965f.cloudfunctions.net/fetchTranscript"


@dataclass
class TranscriptResult:
    """Result of a transcript fetch attempt."""
    video_id: str
    success: bool
    transcript: str | None = None
    error: str | None = None


def fetch_transcript_via_cloud_function(video_id: str) -> TranscriptResult:
    """Fetch transcript via Cloud Function (bypasses YouTube IP blocking)."""
    try:
        response = requests.post(
            CLOUD_FUNCTION_URL,
            json={"data": {"videoId": video_id}},
            timeout=30
        )
        response.raise_for_status()

        data = response.json()

        # Check for error response
        if "error" in data:
            return TranscriptResult(
                video_id=video_id,
                success=False,
                error=f"Cloud Function error: {data['error'].get('message', 'Unknown error')}"
            )

        # Check for successful response
        if "text" in data:
            return TranscriptResult(
                video_id=video_id,
                success=True,
                transcript=data["text"]
            )

        return TranscriptResult(
            video_id=video_id,
            success=False,
            error=f"Unexpected response format: {data}"
        )
    except Exception as e:
        return TranscriptResult(
            video_id=video_id,
            success=False,
            error=f"Cloud Function error: {str(e)}"
        )


def fetch_transcript(video_id: str) -> TranscriptResult:
    """Fetch transcript for a single video.

    Tries Cloud Function first (bypasses IP blocking), falls back to direct API.
    """
    # Try Cloud Function first (more reliable from GitHub Actions)
    result = fetch_transcript_via_cloud_function(video_id)
    if result.success:
        return result

    # Fallback to direct API
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
