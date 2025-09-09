import pytest
from datetime import datetime, timedelta


from src.spotify_tools.duplicates import group_duplicates, build_delete_payload

# -------- helpers --------

def mk_item(
    name: str,
    artists: list[str],
    dur_ms: int,
    uri: str,
    added_at: str,
    *,
    is_local: bool = False,
    typ: str = "track",
    album: str = "Album",
):
    """Build a Spotify-like playlist item dict."""
    return {
        "added_at": added_at,
        "track": {
            "type": typ,
            "is_local": is_local,
            "name": name,
            "artists": [{"name": a} for a in artists],
            "album": {"name": album},
            "uri": uri,
            "duration_ms": dur_ms,
        },
    }


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


# -------- tests --------

def test_relaxed_mode_groups_feat_and_remaster_variants():
    t0 = datetime(2024, 1, 1)
    strictness=False

    items = [
        mk_item("Song (feat. Drake) - Remastered 2012", ["Artist A"], 215000, "spotify:track:111", iso(t0)),
        mk_item("Song", ["Artist A"], 215000, "spotify:track:111", iso(t0 + timedelta(days=1))),
    ]
    groups = group_duplicates(items, strict=strictness, tol_secs=2)
    assert len(groups) == 1
    g = groups[0]
    # 2 tracks in the group, sorted oldest->newest
    assert len(g.tracks) == 2
    assert g.tracks[0].added_at < g.tracks[1].added_at  # newest is last


def test_strict_mode_does_not_group_marker_variants():
    t0 = datetime(2024, 1, 1)
    strictness=True
    items = [
        mk_item("Song (feat. Drake) - Remastered 2012", ["Artist A"], 215000, "spotify:track:111", iso(t0)),
        mk_item("Song", ["Artist A"], 215000, "spotify:track:111", iso(t0 + timedelta(days=1))),
    ]
    groups = group_duplicates(items, strict=strictness, tol_secs=2)
    assert len(groups) == 0  # markers kept => different titles => no group


def test_artist_order_is_insensitive_and_grouped():
    t0 = datetime(2024, 1, 1)
    items = [
        mk_item("Collab", ["A", "B"], 200000, "spotify:track:abc", iso(t0)),
        mk_item("Collab", ["B", "A"], 200000, "spotify:track:abc", iso(t0 + timedelta(hours=1))),
    ]
    groups = group_duplicates(items, strict=False, tol_secs=0)
    assert len(groups) == 1
    assert len(groups[0].tracks) == 2


def test_duration_tolerance_merges_close_lengths_but_not_far():
    t0 = datetime(2024, 1, 1)
    # 214s vs 215s, won't find any duplicates if tolerance is 0 seconds, will find 1 set of duplicates if tolerance is >= 1 second
    near = [
        mk_item("Track X", ["Artist"], 214000, "spotify:track:x", iso(t0)),
        mk_item("Track X", ["Artist"], 215000, "spotify:track:x", iso(t0 + timedelta(seconds=10))),
    ]
    groups0 = group_duplicates(near, strict=False, tol_secs=0)
    groups1 = group_duplicates(near, strict=False, tol_secs=1)
    assert len(groups0) == 0
    assert len(groups1) == 1

    # Far: 214s vs 219s -> even tol=2 should not merge
    far = [
        mk_item("Track Y", ["Artist"], 214000, "spotify:track:y", iso(t0)),
        mk_item("Track Y", ["Artist"], 219000, "spotify:track:y", iso(t0 + timedelta(seconds=10))),
    ]
    groups_far = group_duplicates(far, strict=False, tol_secs=2)
    assert len(groups_far) == 0


def test_skips_non_tracks():
    t0 = datetime(2024, 1, 1)
    items = [
        mk_item("Keep Me", ["Artist"], 180000, "spotify:track:k", iso(t0)),
        mk_item("Keep Me", ["Artist"], 180000, "spotify:track:k", iso(t0 + timedelta(seconds=1))),
        mk_item("Podcast Ep", ["Host"], 1200000, "spotify:episode:e1", iso(t0), typ="episode"),
    ]
    groups = group_duplicates(items, strict=False, tol_secs=0)
    # Only the two identical real tracks should be considered
    assert len(groups) == 1
    assert len(groups[0].tracks) == 2


def test_cjk_titles_preserved_and_not_cross_grouped():
    t0 = datetime(2024, 1, 1)
    # Two copies of the *same* Japanese title (should group)
    items = [
        mk_item("もしも命が描けたら", ["YOASOBI"], 250000, "spotify:track:j1", iso(t0)),
        mk_item("もしも命が描けたら", ["YOASOBI"], 250000, "spotify:track:j1", iso(t0 + timedelta(days=1))),
        # Different Japanese title; should *not* merge with the above
        mk_item("あの夏に咲け", ["美波"], 250000, "spotify:track:j2", iso(t0 + timedelta(days=2))),
    ]
    groups = group_duplicates(items, strict=False, tol_secs=0)
    # Expect exactly one dup group (the two identical titles)
    assert len(groups) == 1
    assert len(groups[0].tracks) == 2
    names_in_group = {t.name for t in groups[0].tracks}
    assert names_in_group == {"もしも命が描けたら"}



