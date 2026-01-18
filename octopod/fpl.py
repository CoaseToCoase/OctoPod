"""FPL API helpers for gameweek data."""

import json
import ssl
import urllib.request
from datetime import datetime
from typing import TypedDict

FPL_BOOTSTRAP_URL = "https://fantasy.premierleague.com/api/bootstrap-static/"


class GameweekInfo(TypedDict):
    id: int
    name: str
    deadline: datetime
    is_current: bool
    is_next: bool
    finished: bool


def _create_ssl_context():
    """Create an SSL context that works on systems with certificate issues."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def fetch_gameweeks() -> list[GameweekInfo]:
    """Fetch all gameweek data from the FPL API."""
    ctx = _create_ssl_context()

    req = urllib.request.Request(
        FPL_BOOTSTRAP_URL,
        headers={"User-Agent": "OctoPod/1.0"}
    )

    with urllib.request.urlopen(req, context=ctx) as response:
        data = json.loads(response.read().decode("utf-8"))

    gameweeks = []
    for event in data.get("events", []):
        deadline = datetime.fromisoformat(event["deadline_time"].replace("Z", "+00:00"))
        gameweeks.append(GameweekInfo(
            id=event["id"],
            name=event["name"],
            deadline=deadline,
            is_current=event["is_current"],
            is_next=event["is_next"],
            finished=event["finished"],
        ))

    return gameweeks


def get_current_gameweek() -> GameweekInfo | None:
    """Get the current gameweek info."""
    gameweeks = fetch_gameweeks()
    for gw in gameweeks:
        if gw["is_current"]:
            return gw
    return None


def get_current_gameweek_deadline() -> datetime | None:
    """Get the deadline of the current gameweek (start of current GW period)."""
    gw = get_current_gameweek()
    if gw:
        return gw["deadline"]
    return None


def get_previous_gameweek_deadline() -> datetime | None:
    """Get the deadline of the previous gameweek (start of videos to fetch)."""
    gameweeks = fetch_gameweeks()
    current_id = None

    for gw in gameweeks:
        if gw["is_current"]:
            current_id = gw["id"]
            break

    if current_id and current_id > 1:
        for gw in gameweeks:
            if gw["id"] == current_id - 1:
                return gw["deadline"]

    return None
