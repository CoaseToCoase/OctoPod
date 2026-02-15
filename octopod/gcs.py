"""Google Cloud Storage upload functionality for OctoPod."""

import json
import os
from datetime import datetime

from .config import get_gcs_config


def upload_summary_to_gcs(gameweek: int, summary: str, video_ids: list[str]) -> str | None:
    """Upload a gameweek summary to Google Cloud Storage.

    Args:
        gameweek: The gameweek number
        summary: The summary markdown text
        video_ids: List of video IDs included in the summary

    Returns:
        The GCS path if successful, None otherwise
    """
    gcs_config = get_gcs_config()
    bucket_name = gcs_config.get("bucket", "")
    path_prefix = gcs_config.get("path_prefix", "octopod/summaries")

    if not bucket_name:
        return None

    # Check for GCS credentials
    credentials_json = os.environ.get("GCS_CREDENTIALS")
    if not credentials_json:
        return None

    try:
        from google.cloud import storage
        from google.oauth2 import service_account

        # Parse credentials from environment variable
        credentials_dict = json.loads(credentials_json)
        credentials = service_account.Credentials.from_service_account_info(
            credentials_dict
        )

        # Create storage client
        client = storage.Client(credentials=credentials)
        bucket = client.bucket(bucket_name)

        # Create the summary data
        summary_data = {
            "gameweek": gameweek,
            "created_at": datetime.now().isoformat(),
            "summary": summary,
            "videos_included": video_ids,
        }

        # Upload JSON version
        json_path = f"{path_prefix}/gw{gameweek}.json"
        json_blob = bucket.blob(json_path)
        json_blob.upload_from_string(
            json.dumps(summary_data, indent=2),
            content_type="application/json"
        )

        # Upload markdown version
        md_path = f"{path_prefix}/gw{gameweek}.md"
        md_content = f"# Gameweek {gameweek} Summary\n\n{summary}"
        md_blob = bucket.blob(md_path)
        md_blob.upload_from_string(md_content, content_type="text/markdown")

        return f"gs://{bucket_name}/{json_path}"

    except ImportError:
        return None
    except Exception:
        return None


def is_gcs_configured() -> bool:
    """Check if GCS is properly configured."""
    gcs_config = get_gcs_config()
    bucket_name = gcs_config.get("bucket", "")
    credentials_json = os.environ.get("GCS_CREDENTIALS")

    return bool(bucket_name and credentials_json)
