#!/usr/bin/env python3
"""Cloud Run entry point - syncs data with GCS and runs pipeline."""

from octopod.data import init_db
from octopod.gcs import sync_data_from_gcs, sync_data_to_gcs, is_gcs_configured
from octopod.channels import fetch_and_store_videos
from octopod.transcripts import fetch_and_store_transcripts
from octopod.analyzer import analyze_and_store_all
from octopod.summarizer import generate_weekly_summary, get_analysis_stats
from octopod.fpl import get_current_gameweek, get_previous_gameweek_deadline


def main():
    print("Initializing...")
    init_db()

    # Sync existing data from GCS
    if is_gcs_configured():
        print("Syncing data from GCS...")
        sync_data_from_gcs()

    # Get gameweek info
    print("Fetching gameweek data...")
    gw = get_current_gameweek()
    since = get_previous_gameweek_deadline()

    if gw:
        print(f"Current gameweek: GW{gw['id']}")
    if since:
        print(f"Fetching videos since: {since}")

    # Fetch videos
    print("\nStep 1/4: Fetching videos...")
    fetch_results = fetch_and_store_videos(since=since)
    total = sum(fetch_results.values())
    print(f"Fetched {total} videos from {len(fetch_results)} channels")

    # Fetch transcripts
    print("\nStep 2/4: Downloading transcripts...")
    transcript_results = fetch_and_store_transcripts()
    print(f"Fetched {len(transcript_results['success'])} transcripts")
    if transcript_results["failed"]:
        print(f"Failed: {len(transcript_results['failed'])}")

    # Analyze
    print("\nStep 3/4: Analyzing transcripts...")
    analysis_results = analyze_and_store_all()
    print(f"Analyzed {len(analysis_results['success'])} videos")
    if analysis_results["failed"]:
        print(f"Failed: {len(analysis_results['failed'])}")

    # Generate summary
    print("\nStep 4/4: Generating summary...")
    stats = get_analysis_stats(days=7)

    if stats["total_videos"] > 0 and gw:
        summary = generate_weekly_summary(gameweek=gw["id"], days=7)
        if summary:
            print(f"\nGenerated GW{gw['id']} summary!")
            print(summary[:500] + "..." if len(summary) > 500 else summary)
    else:
        print("No analyzed videos found for summary")

    # Sync data back to GCS
    if is_gcs_configured():
        print("\nSyncing data to GCS...")
        sync_data_to_gcs()
        print("Done!")


if __name__ == "__main__":
    main()
