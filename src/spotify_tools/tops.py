# tops.py
from __future__ import annotations
from typing import Dict, List, Literal, Optional
import requests

from .client import SpotifyClient, API_URL

TimeRange = Literal["short_term", "medium_term", "long_term"]
Kind = Literal["tracks", "artists"]

def _user_get(client: SpotifyClient, path: str, params: Optional[Dict] = None) -> Dict:
    # Force user-token header for /me endpoints
    headers = client._auth_header(write=True)
    r = requests.get(f"{API_URL}{path}", headers=headers, params=params or {}, timeout=30)
    r.raise_for_status()
    return r.json()

def get_user_top(client: SpotifyClient, kind: Kind, time_range: TimeRange = "short_term", limit: int = 5) -> List[Dict]:
    """
    Fetch user's top tracks or artists.
    Requires 'user-top-read' scope.
    """
    kind = kind if kind in ("tracks", "artists") else "tracks"
    tr = time_range if time_range in ("short_term", "medium_term", "long_term") else "short_term"
    limit = max(1, min(50, int(limit)))
    data = _user_get(client, f"/me/top/{kind}", params={"limit": limit, "time_range": tr})
    return data.get("items", [])

def print_top_tracks(items: List[Dict]) -> None:
    print("\nYour Top Tracks:")
    for i, t in enumerate(items[:5], 1):
        name = t.get("name", "")
        artists = ", ".join([a.get("name", "") for a in t.get("artists", [])])
        album = (t.get("album") or {}).get("name", "")
        print(f"[{i}] {name} — {artists}. Album: ({album})")

def print_top_artists(items: List[Dict]) -> None:
    print("\nYour Top Artists:")
    for i, a in enumerate(items[:5], 1):
        name = a.get("name", "")
        genres = ", ".join(a.get("genres", [])[:3])
        print(f"[{i}] {name}. Genres: [{genres}]")

def interactive_run(client: SpotifyClient) -> None:
    print("\n=== Top 5 Tracks / Artists ===")
    print("Choose time range:")
    print("  1) Last 4 weeks (short_term)")
    print("  2) Last 6 months (medium_term)")
    print("  3) All time (long_term)")
    tr_choice = (input("Enter 1-3: ").strip() or "1")
    if (int(tr_choice) > 3 or int(tr_choice) < 1): 
        print("Invalid input, defaulting to 4 week time horizon")
        
    time_range = {"1": "short_term", "2": "medium_term", "3": "long_term"}.get(tr_choice, "short_term")

    print("Choose type:")
    print("  1) Tracks")
    print("  2) Artists")
    kind_choice = (input("Enter 1 or 2: ").strip() or "1")
    if (int(kind_choice) != 1 and int(kind_choice) != 2): 
        print("Invalid input, defaulting to Tracks")

    kind = "tracks" if kind_choice == "1" else "artists"

    items = get_user_top(client, kind=kind, time_range=time_range, limit=5)
    if kind == "tracks":
        print_top_tracks(items)
    else:
        print_top_artists(items)
