"""Google Cloud Storage functionality for OctoPod."""

import json
import os
from datetime import datetime
from pathlib import Path

from .config import get_gcs_config, get_profile_data_dir


def upload_summary_to_gcs(period: str, summary: str, video_ids: list[str]) -> str | None:
    """Upload a period summary to Google Cloud Storage.

    Args:
        period: The period identifier (e.g., "gw26", "2024-w05")
        summary: The summary markdown text
        video_ids: List of video IDs included in the summary

    Returns:
        The GCS path if successful, None otherwise
    """
    gcs_config = get_gcs_config()
    bucket_name = gcs_config.get("bucket", "")
    path_prefix = gcs_config.get("path_prefix", "octopod")

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
            "period": period,
            "created_at": datetime.now().isoformat(),
            "summary": summary,
            "videos_included": video_ids,
        }

        # Upload JSON version
        json_path = f"{path_prefix}/summaries/{period}.json"
        json_blob = bucket.blob(json_path)
        json_blob.upload_from_string(
            json.dumps(summary_data, indent=2),
            content_type="application/json"
        )

        # Upload markdown version
        md_path = f"{path_prefix}/summaries/{period}.md"
        md_content = f"# {period.upper()} Summary\n\n{summary}"
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


def _get_gcs_client():
    """Get authenticated GCS client."""
    from google.cloud import storage
    from google.oauth2 import service_account

    credentials_json = os.environ.get("GCS_CREDENTIALS")
    if not credentials_json:
        return None

    credentials_dict = json.loads(credentials_json)
    credentials = service_account.Credentials.from_service_account_info(
        credentials_dict
    )
    return storage.Client(credentials=credentials)


def sync_data_from_gcs() -> bool:
    """Download data files from GCS to local for the current profile."""
    if not is_gcs_configured():
        return False

    try:
        gcs_config = get_gcs_config()
        bucket_name = gcs_config.get("bucket", "")
        path_prefix = gcs_config.get("path_prefix", "octopod")
        data_prefix = f"{path_prefix}/data"

        client = _get_gcs_client()
        if not client:
            return False

        bucket = client.bucket(bucket_name)
        profile_data_dir = get_profile_data_dir()
        profile_data_dir.mkdir(parents=True, exist_ok=True)

        # Download videos.json and analyses.json
        for filename in ["videos.json", "analyses.json"]:
            blob = bucket.blob(f"{data_prefix}/{filename}")
            local_path = profile_data_dir / filename
            if blob.exists():
                blob.download_to_filename(str(local_path))

        return True

    except Exception:
        return False


def upload_analysis_to_gcs(video_id: str, video_title: str, channel_name: str, analysis_data: dict, category: str) -> str | None:
    """Upload individual video analysis to GCS.

    Args:
        video_id: YouTube video ID
        video_title: Video title
        channel_name: Channel name
        analysis_data: Analysis result dictionary
        category: Category name (e.g., "FPL Draft")

    Returns:
        The GCS path if successful, None otherwise
    """
    if not is_gcs_configured():
        return None

    try:
        gcs_config = get_gcs_config()
        bucket_name = gcs_config.get("bucket", "")
        path_prefix = gcs_config.get("path_prefix", "octopod")

        client = _get_gcs_client()
        if not client:
            return None

        bucket = client.bucket(bucket_name)

        # Create report data
        report = {
            "video_id": video_id,
            "title": video_title,
            "channel": channel_name,
            "category": category,
            "analyzed_at": datetime.now().isoformat(),
            "analysis": analysis_data
        }

        # File path: reports/{category}/{date}_{video_id}.json
        date_str = datetime.now().strftime("%Y-%m-%d")
        safe_category = category.replace(" ", "_")
        json_path = f"{path_prefix}/{safe_category}/{date_str}_{video_id}.json"

        # Upload to GCS
        blob = bucket.blob(json_path)
        blob.upload_from_string(
            json.dumps(report, indent=2),
            content_type="application/json"
        )

        return f"gs://{bucket_name}/{json_path}"

    except Exception as e:
        print(f"Error uploading to GCS: {e}")
        return None


def sync_data_to_gcs() -> bool:
    """Upload data files from local to GCS for the current profile."""
    if not is_gcs_configured():
        return False

    try:
        gcs_config = get_gcs_config()
        bucket_name = gcs_config.get("bucket", "")
        path_prefix = gcs_config.get("path_prefix", "octopod")
        data_prefix = f"{path_prefix}/data"

        client = _get_gcs_client()
        if not client:
            return False

        bucket = client.bucket(bucket_name)
        profile_data_dir = get_profile_data_dir()

        # Upload videos.json and analyses.json
        for filename in ["videos.json", "analyses.json"]:
            local_path = profile_data_dir / filename
            if local_path.exists():
                blob = bucket.blob(f"{data_prefix}/{filename}")
                blob.upload_from_filename(str(local_path))

        return True

    except Exception:
        return False
