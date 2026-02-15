"""CLI entry point for OctoPod."""

from datetime import datetime
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown

from .config import set_profile, get_profile, list_profiles
from .data import (
    init_db,
    get_all_channels,
    get_all_videos,
    get_videos_without_transcripts,
    get_videos_without_analysis,
)
from .channels import fetch_and_store_videos
from .transcripts import fetch_and_store_transcripts
from .analyzer import analyze_and_store_all
from .summarizer import generate_weekly_summary, get_analysis_stats
from .fpl import get_previous_gameweek_deadline, get_current_gameweek

app = typer.Typer(
    name="octopod",
    help="Podcast Analyzer - Download and analyze YouTube transcripts"
)
channels_app = typer.Typer(help="Manage podcast channels")
app.add_typer(channels_app, name="channels")

console = Console()


@app.callback()
def main(
    profile: Optional[str] = typer.Option(
        None, "--profile", "-p",
        help="Profile to use (e.g., draft-fpl, politics). Uses default if not specified."
    )
):
    """OctoPod - Multi-profile podcast analyzer."""
    if profile:
        try:
            set_profile(profile)
        except FileNotFoundError as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(1)


def ensure_db():
    """Ensure database is initialized."""
    init_db()


@app.command()
def fetch(
    since: datetime = typer.Option(None, "--since", "-s", help="Only fetch videos published after this date (YYYY-MM-DD)"),
    current_gw: bool = typer.Option(False, "--current-gw", "-g", help="Only fetch videos since the previous gameweek deadline")
):
    """Fetch latest videos from all channels."""
    ensure_db()

    # Determine the since date
    filter_date = since
    if current_gw:
        with console.status("[bold green]Fetching gameweek data from FPL API..."):
            filter_date = get_previous_gameweek_deadline()
            gw = get_current_gameweek()
        if filter_date:
            console.print(f"[cyan]Filtering videos since GW{gw['id'] - 1 if gw else '?'} deadline: {filter_date.strftime('%Y-%m-%d %H:%M')} UTC[/cyan]")
        else:
            console.print("[yellow]Could not determine previous gameweek deadline, fetching all videos.[/yellow]")

    with console.status("[bold green]Fetching videos from channels..."):
        results = fetch_and_store_videos(since=filter_date)

    table = Table(title="Videos Fetched" + (f" (since {filter_date.strftime('%Y-%m-%d')})" if filter_date else ""))
    table.add_column("Channel", style="cyan")
    table.add_column("Videos Found", justify="right", style="green")

    total = 0
    for channel_name, count in results.items():
        table.add_row(channel_name, str(count))
        total += count

    table.add_row("", "")
    table.add_row("[bold]Total[/bold]", f"[bold]{total}[/bold]")

    console.print(table)


@app.command()
def transcripts():
    """Download transcripts for videos that don't have them."""
    ensure_db()

    videos = get_videos_without_transcripts()
    if not videos:
        console.print("[yellow]No videos need transcripts.[/yellow]")
        return

    console.print(f"[cyan]Found {len(videos)} videos without transcripts.[/cyan]")

    with console.status("[bold green]Fetching transcripts..."):
        results = fetch_and_store_transcripts()

    success_count = len(results["success"])
    failed_count = len(results["failed"])

    console.print(f"[green]Successfully fetched: {success_count}[/green]")

    if failed_count > 0:
        console.print(f"[red]Failed: {failed_count}[/red]")
        for result in results["failed"]:
            console.print(f"  [dim]- {result.video_id}: {result.error}[/dim]")


@app.command()
def analyze():
    """Analyze transcripts that haven't been analyzed yet."""
    ensure_db()

    videos = get_videos_without_analysis()
    if not videos:
        console.print("[yellow]No videos need analysis.[/yellow]")
        return

    console.print(f"[cyan]Found {len(videos)} videos to analyze.[/cyan]")

    with console.status("[bold green]Analyzing transcripts with Claude..."):
        results = analyze_and_store_all()

    success_count = len(results["success"])
    failed_count = len(results["failed"])

    console.print(f"[green]Successfully analyzed: {success_count}[/green]")

    if failed_count > 0:
        console.print(f"[red]Failed: {failed_count}[/red]")
        for result in results["failed"]:
            console.print(f"  [dim]- {result.video_id}: {result.error}[/dim]")


@app.command()
def summary(
    gameweek: int = typer.Option(None, "--gameweek", "-g", help="Gameweek number (auto-detected if not provided)")
):
    """Generate a gameweek summary from analyses since the previous GW deadline."""
    ensure_db()

    # Auto-detect gameweek
    if gameweek is None:
        gw = get_current_gameweek()
        if gw:
            gameweek = gw["id"]
        else:
            console.print("[red]Could not detect gameweek. Please provide --gameweek option.[/red]")
            return

    stats = get_analysis_stats()

    if stats["total_videos"] == 0:
        console.print("[yellow]No analyzed videos found since previous gameweek deadline.[/yellow]")
        console.print("[dim]Run 'octopod fetch', 'octopod transcripts', and 'octopod analyze' first.[/dim]")
        return

    console.print(f"[cyan]Generating GW{gameweek} summary from {stats['total_videos']} videos across {len(stats['channels'])} channels...[/cyan]")

    with console.status("[bold green]Generating summary with Claude..."):
        summary_text = generate_weekly_summary(gameweek=gameweek)

    if summary_text:
        console.print()
        console.print(Panel(
            Markdown(summary_text),
            title=f"[bold]Gameweek {gameweek} Summary[/bold]",
            border_style="green"
        ))
    else:
        console.print("[red]Failed to generate summary.[/red]")


@app.command()
def run(
    gameweek: int = typer.Option(None, "--gameweek", "-gw", help="Gameweek number (auto-detected if not provided)"),
    since: datetime = typer.Option(None, "--since", "-s", help="Only fetch videos published after this date (YYYY-MM-DD)"),
    current_gw: bool = typer.Option(True, "--current-gw/--all", help="Only fetch videos since previous gameweek deadline (default: true)")
):
    """Run the full pipeline: fetch, transcripts, analyze, and summarize."""
    ensure_db()
    console.print(f"[bold]Profile: {get_profile()}[/bold]\n")

    # Determine the since date and gameweek
    filter_date = since
    detected_gw = None

    if current_gw and since is None:
        with console.status("[bold green]Fetching gameweek data from FPL API..."):
            filter_date = get_previous_gameweek_deadline()
            detected_gw = get_current_gameweek()
        if filter_date and detected_gw:
            console.print(f"[cyan]Current gameweek: GW{detected_gw['id']}[/cyan]")
            console.print(f"[cyan]Filtering videos since GW{detected_gw['id'] - 1} deadline: {filter_date.strftime('%Y-%m-%d %H:%M')} UTC[/cyan]")

    # Use detected gameweek if not provided
    if gameweek is None:
        if detected_gw:
            gameweek = detected_gw["id"]
        else:
            console.print("[red]Could not detect gameweek. Please provide --gameweek option.[/red]")
            raise typer.Exit(1)

    # Fetch videos
    console.print("\n[bold cyan]Step 1/4: Fetching videos...[/bold cyan]")
    with console.status("[bold green]Fetching videos from channels..."):
        fetch_results = fetch_and_store_videos(since=filter_date)

    total_fetched = sum(fetch_results.values())
    console.print(f"[green]Fetched {total_fetched} videos from {len(fetch_results)} channels.[/green]")

    # Fetch transcripts
    console.print("\n[bold cyan]Step 2/4: Downloading transcripts...[/bold cyan]")
    videos_need_transcripts = get_videos_without_transcripts()

    if videos_need_transcripts:
        with console.status("[bold green]Fetching transcripts..."):
            transcript_results = fetch_and_store_transcripts()
        console.print(f"[green]Fetched {len(transcript_results['success'])} transcripts.[/green]")
        if transcript_results["failed"]:
            console.print(f"[yellow]Failed to fetch {len(transcript_results['failed'])} transcripts.[/yellow]")
    else:
        console.print("[dim]No new transcripts needed.[/dim]")

    # Analyze
    console.print("\n[bold cyan]Step 3/4: Analyzing transcripts...[/bold cyan]")
    videos_need_analysis = get_videos_without_analysis()

    if videos_need_analysis:
        with console.status("[bold green]Analyzing transcripts with Claude..."):
            analysis_results = analyze_and_store_all()
        console.print(f"[green]Analyzed {len(analysis_results['success'])} videos.[/green]")
        if analysis_results["failed"]:
            console.print(f"[yellow]Failed to analyze {len(analysis_results['failed'])} videos.[/yellow]")
    else:
        console.print("[dim]No new analysis needed.[/dim]")

    # Generate summary
    console.print("\n[bold cyan]Step 4/4: Generating summary...[/bold cyan]")
    stats = get_analysis_stats()

    if stats["total_videos"] == 0:
        console.print("[yellow]No analyzed videos found since previous gameweek deadline.[/yellow]")
        return

    with console.status("[bold green]Generating summary with Claude..."):
        summary_text = generate_weekly_summary(gameweek=gameweek)

    if summary_text:
        console.print()
        console.print(Panel(
            Markdown(summary_text),
            title=f"[bold]Gameweek {gameweek} Summary[/bold]",
            border_style="green"
        ))
    else:
        console.print("[red]Failed to generate summary.[/red]")


@app.command()
def videos(
    limit: int = typer.Option(20, "--limit", "-l", help="Number of videos to show")
):
    """List recent videos in the database."""
    ensure_db()

    all_videos = get_all_videos(limit=limit)

    if not all_videos:
        console.print("[yellow]No videos in database. Run 'octopod fetch' first.[/yellow]")
        return

    table = Table(title=f"Recent Videos (showing {len(all_videos)})")
    table.add_column("ID", style="dim", max_width=12)
    table.add_column("Channel", style="cyan")
    table.add_column("Title", max_width=50)
    table.add_column("Published", style="green")
    table.add_column("Transcript", justify="center")
    table.add_column("Analyzed", justify="center")

    for video in all_videos:
        has_transcript = "[green]Yes[/green]" if video["transcript"] else "[red]No[/red]"
        has_analysis = "[green]Yes[/green]" if video["has_analysis"] else "[red]No[/red]"
        published = str(video["published_at"])[:10] if video["published_at"] else "Unknown"

        table.add_row(
            video["id"][:11] + "...",
            video["channel_name"],
            video["title"][:50],
            published,
            has_transcript,
            has_analysis
        )

    console.print(table)


@channels_app.command("list")
def list_channels():
    """List all configured channels."""
    ensure_db()

    channels = get_all_channels()

    table = Table(title="Configured Channels")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("YouTube Channel ID", style="dim")

    for channel in channels:
        table.add_row(
            channel["id"],
            channel["name"],
            channel["youtube_channel_id"]
        )

    console.print(table)


@channels_app.command("add")
def add_channel_cmd(
    name: str = typer.Argument(..., help="Channel display name"),
    youtube_id: str = typer.Argument(..., help="YouTube channel ID")
):
    """Add a new channel (prints instructions - channels are managed in config.yaml)."""
    console.print("[yellow]Channels are now managed in config.yaml[/yellow]")
    console.print("\nTo add a channel, edit config.yaml and add an entry like:")
    console.print(f"""
[cyan]  - id: {name.lower().replace(" ", "_").replace("-", "_")}
    name: {name}
    youtube_channel_id: {youtube_id}[/cyan]
""")


@app.command()
def init():
    """Initialize the data files for the current profile."""
    init_db()
    profile = get_profile()
    console.print(f"[green]Data files initialized successfully for profile: {profile}[/green]")
    console.print(f"[dim]Data location: data/{profile}/videos.json, data/{profile}/analyses.json, data/{profile}/summaries/[/dim]")


@app.command()
def profiles():
    """List all available profiles."""
    available = list_profiles()
    current = get_profile()

    if not available:
        console.print("[yellow]No profiles found. Create a YAML file in config/ directory.[/yellow]")
        return

    table = Table(title="Available Profiles")
    table.add_column("Profile", style="cyan")
    table.add_column("Active", justify="center")

    for p in sorted(available):
        is_active = "[green]✓[/green]" if p == current else ""
        table.add_row(p, is_active)

    console.print(table)
    console.print("\n[dim]Use --profile <name> to switch profiles[/dim]")


if __name__ == "__main__":
    app()
