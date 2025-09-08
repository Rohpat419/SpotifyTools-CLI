from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple
from .normalize import normalize_title, normalize_artists

DEFAULT_TOLERANCE=2

KeyFormat = Tuple[str, Tuple[str, ...], int] 

# Use dataclass because all fields are going to be filled
@dataclass 
class Track: 
    name: str
    artists: List[str]
    album: str
    uri: str
    duration_ms: int
    added_at: str
    
    playlist_idx: int

@dataclass
# one group of duplicated tracks
class DuplicateGroup: 
    key: KeyFormat # (title, artists[], duration_seconds)
    tracks: List[Track]

def _round_seconds(ms: int) -> int: 
    return int(round(ms / 1000.0))

# The key is the fully normalized version of a song, used to identify if two are duplicates
# COME BACK TO THIS if we want to handle the case where a feature is just not mentioned in the new/old release of a song, maybe include that into STRICT
def make_key(t: Track, strict: bool) -> Tuple[str, Tuple[str, ...], int]: 
    title = normalize_title(t.name, strict=strict)
    artists = tuple(normalize_artists(t.artists))
    rounded = _round_seconds(t.duration_ms)
    return (title, artists, rounded)

# Be willing to group songs together if they fall within tolerance
def within_tolerance(sec_a: int, sec_b: int, tol: int) -> bool: 
    return abs(sec_a-sec_b) <= tol


def group_duplicates(items: Iterable[dict], *, strict: bool = False, tol_secs: int = DEFAULT_TOLERANCE) -> List[DuplicateGroup]: 
    tracks: List[Track] = []
    for pos, item in enumerate(items): 
        track = item.get("track") or {}
        if not track or track.get("type") != "track":
            continue
        name = track.get("name") or ""
        artists = [a.get("name", "") for a in track.get("artists", [])]
        album = (track.get("album") or {}).get("name", "")
        uri = track.get("uri") or ""
        duration = int(track.get("duration_ms") or 0)
        added_at = item.get("added_at") or ""
        tracks.append(Track(name, artists, album, uri, duration, added_at, pos))

    buckets: Dict[KeyFormat, List[Track]] = {}
    for track in tracks: 
        key = make_key(track, strict)
        buckets.setdefault(key, []).append(track)

    # tolerance code. Very inefficient, n^2 COME BACK IF SLOW
    merged: Dict[KeyFormat, List[Track]] = {}
    # iterate through the unique keys in buckets, for each key, check if it matches closely enough with an already placed key in the merged List
    for (title, artists, sec), group in buckets.items():
        placed = False
        for existingKey in list(merged.keys()):
            title2, artists2, seconds2 = existingKey
            if title2 == title and artists2 == artists and within_tolerance(sec, seconds2, tol_secs):
                merged[existingKey].extend(group)
                placed = True
                break
        # create new group if no matches found
        if not placed: 
            merged[(title, artists, sec)] = group
    
    # Generate the DuplicateGroups to be handled by deletion code. Order the tracks in a duplicate group so the latest add comes last
    out: List[DuplicateGroup] = []
    for key, group in merged.items():
        if len(group) > 1: 
            group.sort(key=lambda x: x.added_at) 
            out.append(DuplicateGroup(key, group))
    
    return out


# Delete payload returns {"tracks": [{uri, positions[]}, {uri, positions[] }] }. 
def build_delete_payload(groups: List[DuplicateGroup]) -> dict: 
    tracks_payload: List[dict] = []
    for group in groups: 
        if len(group.tracks) <= 1:
            continue
        keep = group.tracks[0] # keep oldest track, "This is when I first discovered this track"
        to_remove = [t for t in group.tracks if t is not keep]
        position_by_uri: Dict[str, List[int]] = {}
        # track both the uri and playlist idx of duplicates, both are used to coordinate a delete
        for track in to_remove: 
            position_by_uri.setdefault(track.uri, []).append(track.playlist_idx)
        for uri, positions in position_by_uri.items(): 
            tracks_payload.append({"uri": uri, "positions": positions})
    # package into this format that the endpoint is expecting
    return {"tracks": tracks_payload}

