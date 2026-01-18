"""Claude API analysis for FPL podcast transcripts."""

import json
from dataclasses import dataclass

import anthropic

from .config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL
from .database import get_videos_without_analysis, save_analysis


ANALYSIS_PROMPT = """You are an expert Fantasy Premier League (FPL) analyst. Analyze the following podcast transcript and extract key information relevant to FPL Draft managers.

Focus on extracting:
1. **Player Mentions**: Any players mentioned with context about their form, fixtures, or potential
2. **Recommendations**: Buy/sell/hold/avoid recommendations for specific players
3. **Injury News**: Any injury updates, return timelines, or fitness concerns
4. **Differential Picks**: Players mentioned as differentials or under-the-radar options
5. **Captain Suggestions**: Any captaincy recommendations

Return your analysis as a JSON object with this exact structure:
{{
    "player_mentions": [
        {{
            "player": "Player Name",
            "team": "Team Name",
            "context": "What was said about them",
            "sentiment": "positive|negative|neutral"
        }}
    ],
    "recommendations": [
        {{
            "player": "Player Name",
            "team": "Team Name",
            "action": "buy|sell|hold|avoid",
            "reason": "Why this recommendation was made"
        }}
    ],
    "injury_news": [
        {{
            "player": "Player Name",
            "team": "Team Name",
            "status": "injured|doubtful|returning|fit",
            "details": "Injury details or return timeline"
        }}
    ],
    "differentials": [
        {{
            "player": "Player Name",
            "team": "Team Name",
            "reason": "Why they're a good differential"
        }}
    ],
    "captain_picks": [
        {{
            "player": "Player Name",
            "team": "Team Name",
            "reason": "Why they're a good captain choice"
        }}
    ]
}}

Important:
- Only include information that is explicitly mentioned in the transcript
- If a category has no relevant mentions, return an empty array for that category
- Be specific about what was actually said, don't make assumptions
- Include the team name when it's mentioned or can be reasonably inferred

Transcript from "{title}" by {channel}:

{transcript}

Return ONLY the JSON object, no additional text."""


@dataclass
class AnalysisResult:
    """Result of analyzing a video transcript."""
    video_id: str
    success: bool
    player_mentions: list[dict] | None = None
    recommendations: list[dict] | None = None
    injury_news: list[dict] | None = None
    raw_analysis: str | None = None
    error: str | None = None


def analyze_transcript(
    video_id: str,
    title: str,
    channel_name: str,
    transcript: str
) -> AnalysisResult:
    """Analyze a transcript using Claude API."""
    if not ANTHROPIC_API_KEY:
        return AnalysisResult(
            video_id=video_id,
            success=False,
            error="ANTHROPIC_API_KEY environment variable not set"
        )

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    # Truncate very long transcripts to avoid token limits
    max_transcript_length = 100000
    if len(transcript) > max_transcript_length:
        transcript = transcript[:max_transcript_length] + "... [truncated]"

    prompt = ANALYSIS_PROMPT.format(
        title=title,
        channel=channel_name,
        transcript=transcript
    )

    try:
        message = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=4096,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        response_text = message.content[0].text

        # Parse the JSON response
        # Handle potential markdown code blocks
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            # Remove first and last lines (```json and ```)
            response_text = "\n".join(lines[1:-1])

        analysis = json.loads(response_text)

        return AnalysisResult(
            video_id=video_id,
            success=True,
            player_mentions=analysis.get("player_mentions", []),
            recommendations=analysis.get("recommendations", []),
            injury_news=analysis.get("injury_news", []),
            raw_analysis=response_text
        )

    except json.JSONDecodeError as e:
        return AnalysisResult(
            video_id=video_id,
            success=False,
            error=f"Failed to parse JSON response: {e}",
            raw_analysis=response_text if "response_text" in locals() else None
        )
    except anthropic.APIError as e:
        return AnalysisResult(
            video_id=video_id,
            success=False,
            error=f"Anthropic API error: {e}"
        )
    except Exception as e:
        return AnalysisResult(
            video_id=video_id,
            success=False,
            error=str(e)
        )


def analyze_and_store_all() -> dict[str, list[AnalysisResult]]:
    """Analyze all videos with transcripts that haven't been analyzed yet."""
    videos = get_videos_without_analysis()
    results: dict[str, list[AnalysisResult]] = {
        "success": [],
        "failed": []
    }

    for video in videos:
        result = analyze_transcript(
            video_id=video["id"],
            title=video["title"],
            channel_name=video["channel_name"],
            transcript=video["transcript"]
        )

        if result.success:
            save_analysis(
                video_id=video["id"],
                player_mentions=result.player_mentions or [],
                recommendations=result.recommendations or [],
                injury_news=result.injury_news or [],
                raw_analysis=result.raw_analysis or ""
            )
            results["success"].append(result)
        else:
            results["failed"].append(result)

    return results
