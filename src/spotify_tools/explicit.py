
from __future__ import annotations
import re, html
from typing import Dict, Iterable, List, Optional

import requests

from .client import SpotifyClient, API_URL

_session = requests.Session()

_LI_RE = re.compile(r"<li>\s*([^<>\r\n]+?)\s*</li>", re.IGNORECASE)
_WORDLIKE_RE = re.compile(r"^[a-z][a-z0-9' -]*$")  # keep plain word-ish entries
_TOKEN_RE = re.compile(r"[A-Za-z']+")               # tokenize lyrics into words

def _parse_purgomalum_html_to_set(html_text: str) -> set[str]:
    """Extract <li>...</li> entries, unescape & normalize."""
    txt = html.unescape(html_text)
    words: set[str] = set()
    for m in _LI_RE.finditer(txt):
        w = m.group(1).strip().lower()
        if _WORDLIKE_RE.fullmatch(w):
            words.add(w)
    return words

def load_banned_words_from_purgomalum() -> set[str]:
    """Fetch and parse the public profanity list HTML once.
    It's about 200 words. 
    """
    
    r = _session.get("https://www.purgomalum.com/profanitylist.html", timeout=15)
    r.raise_for_status()
    return _parse_purgomalum_html_to_set(r.text)




def _normalize_words(s: str) -> List[str]:
    return [w.lower() for w in _TOKEN_RE.findall(s or "")]

def fetch_lyrics_lrclib(artist: str, title: str, duration_ms: Optional[int] = None) -> Optional[str]:
    """
    Try LRCLIB public API for lyrics. No auth required.
    Returns plain text lyrics if available, else None.
    """
    try:
        params = {"track_name": title, "artist_name": artist}
        if duration_ms:
            params["duration"] = int(round(duration_ms / 1000))
        r = _session.get("https://lrclib.net/api/get", params=params, timeout=15)
        if r.status_code == 200 and isinstance(r.json(), dict):
            data = r.json()
            txt = data.get("plainLyrics") or data.get("syncedLyrics") or ""
            # strip timestamps if synced
            txt = re.sub(r"\[[0-9:\.]+\]", " ", txt)
            return txt.strip() or None
        return None
    except Exception:
        return None

def scan_lyrics_for_words(lyrics: str, banned: Iterable[str]) -> List[str]:
    words = set(_normalize_words(lyrics))
    banned_norm = {b.lower() for b in banned}
    return sorted(list(words.intersection(banned_norm)))

def explicit_report_from_playlist(
    client: SpotifyClient,
    playlist_id: str,
    mode: str = "metadata",          # "metadata" or "lyrics"
    extra_banned_words: Optional[Iterable[str]] = None,
) -> List[Dict]:
    """
    Build a report of explicit songs from a playlist.
    - metadata: rely on Spotify 'explicit' flag
    - lyrics: LRCLIB scan; fallback to metadata if no lyrics found
    """

    banned = set(load_banned_words_from_purgomalum())
    if extra_banned_words:
        banned |= {w.lower() for w in extra_banned_words if w}

    try: 
        items = list(client.iter_playlist_items(playlist_id, write=False))
    except requests.HTTPError as e:
        status = getattr(e.response, "status_code", None) 
        if status in (401, 404): 
            print("Playlist may be private or restricted; retrying with user auth...")
            items = list(client.iter_playlist_items(playlist_id, write=True))
            print("User auth succeeded, starting scans now\n")
        else: 
            raise

    print(f"\nScanning {len(items)} tracks...")
    out: List[Dict] = []
    for idx, item in enumerate(items, 1):
        track = item.get("track") or {}
        if not track or track.get("type") != "track":
            continue

        name = track.get("name") or ""
        artists = [a.get("name", "") for a in track.get("artists", [])]
        artist_primary = artists[0] if artists else ""
        uri = track.get("uri")
        duration_ms = int(track.get("duration_ms") or 0)
        explicit_flag = bool(track.get("explicit"))

        if mode == "metadata":
            if explicit_flag:
                out.append({
                    "name": name,
                    "artists": artists,
                    "uri": uri,
                    "reason": "spotify_metadata_explicit_flag"
                })
        else:
            if explicit_flag:
                out.append({
                    "name": name,
                    "artists": artists,
                    "uri": uri,
                    "reason": "spotify_metadata_explicit_flag"
                })
                continue # Do not hit the lrclib endpoint if song already marked explicit

            lyrics = fetch_lyrics_lrclib(artist_primary, name, duration_ms)
            if lyrics:
                hits = scan_lyrics_for_words(lyrics, banned)
                if hits:
                    out.append({
                        "name": name,
                        "artists": artists,
                        "uri": uri,
                        "reason": f"lyrics_banned_words:{','.join(hits)}"
                    })
            elif not lyrics:
                print("Lyrics could not be found for the following song:")
                print(f"{name} - {', '.join(artists)}\n")



        if idx % 25 == 0 or idx == len(items): 
            print(f"Processed {idx}/{len(items)} tracks\n")
    return out

def print_explicit_report(rows: List[Dict]) -> None:
    if not rows:
        print("No explicit songs found given selected mode/wordlist.")
        return
    print(f"Found {len(rows)} potentially explicit songs:\n")
    for i, r in enumerate(rows, 1):
        print(f"[{i}] {r['name']} — {', '.join(r['artists'])}  ({r['reason']})")
    print("")

def interactive_run(client: SpotifyClient) -> None:
    print("\n=== Explicit Content Filter ===")
    playlist = input("Paste playlist URL or ID: ").strip()
    print("Choose mode:")
    print("  1) Fast (Spotify 'explicit' flag only)")
    print("  2) Lyrics scan (LRCLIB) + fallback to metadata flag")
    choice = (input("Enter 1 or 2: ").strip() or "1")
    mode = "metadata" if choice == "1" else "lyrics"
    
    extra_words = None
    # do not allow lyrics in the metadata mode because the lyric library is slow
    if mode == "lyrics":
        add_words = input("Add comma-separated extra banned words (optional): ").strip()
        extra_words = [w.strip() for w in add_words.split(",")] if add_words else None

    rows = explicit_report_from_playlist(client, playlist, mode=mode, extra_banned_words=extra_words)
    print_explicit_report(rows)

    # Give user choice to scrub playlist if explicit songs detected
    if not rows: 
        return 

    print("What would you like to do with explicit songs?")
    print("  1) Do nothing")
    print("  2) Construct a NEW playlist with only clean songs")
    print("  3) Delete the explicit songs from the given playlist")
    action = input("Enter 1/2/3: ").strip() or "1"

    explicit_uris = {r["uri"] for r in rows if r.get("uri")}
    # Fetch all tracks in the original playlist so we know the clean ones
    items = list(client.iter_playlist_items(playlist, write=True))
    all_uris = [t.get("track", {}).get("uri") for t in items if t.get("track")]
    clean_uris = [u for u in all_uris if u and u not in explicit_uris]

    if action == "2":
        user_id = client.get_current_user_id()
        old_playlist_name = client.playlist_name_from_id(playlist, write=False)
        new_playlist_name = f"Clean version of {old_playlist_name}" if old_playlist_name else "Clean Version"
        new_id = client.create_playlist(user_id, name=new_playlist_name, description=f"Filtered copy of {playlist}", public=False)
        # Spotify limits to 100 per add_items
        for i in range(0, len(clean_uris), 100):
            client.add_items(new_id, clean_uris[i:i+100])
        print(f"Created new clean playlist: {new_id}")

    elif action == "3":
        # Remove explicit songs in chunks
        uris_to_remove = list(explicit_uris)
        for i in range(0, len(uris_to_remove), 100):
            client.remove_by_uri(playlist, uris_to_remove[i:i+100])
        print(f"Removed {len(explicit_uris)} explicit songs from playlist.")


