# Run the cli version of the app, meant to be replaced by the web app
import argparse, csv, json
from pathlib import Path
from typing import Any, Dict, List

from .client import SpotifyClient
from .duplicates import group_duplicates, build_delete_payload, DEFAULT_TOLERANCE

def _write_json(path: Path, data: Any) -> None: 
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _write_csv(path: Path, groups) -> None: 
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f: 
        w = csv.writer(f)
        w.writerow(["group_key", "name", "artists", "album", "uri", "added_at", "duration_ms"])
        for g in groups: 
            key = "|".join([g.key[0], ",".join(g.key[1]), str(g.key[2])])
            for t in g.tracks:
                w.writerow([key, t.name, ", ".join(t.artists), t.album, t.uri, t.added_at, t.duration_ms])            

def cmd_check(args) -> int: 
    client = SpotifyClient()
    items = list(client.iter_playlist_items(args.playlist, write=False))
    groups = group_duplicates(items, strict=args.strict, tol_secs=DEFAULT_TOLERANCE)

    # total number of duplicates is the number of tracks in all the groups - number of groups since each group has 1 non-duplicate
    num_duplicates = sum(len(group.tracks) for group in groups) - len(groups)
    print(f"Found {num_duplicates} Duplicate tracks in {len(groups)} Duplicate groups")


    for idx, group in enumerate(groups, 1):
        names = {t.name for t in group.tracks}
        artists = {", ".join(t.artists) for t in group.tracks}
        print(f"[{idx}] {list(names)[0]} — {list(artists)[0]}  (x{len(group.tracks)})")

    if args.json: 
        _write_json(Path(args.json), [
            {   
                "key": {"title": g.key[0], "artists": list(g.key[1]), "rounded_sec": g.key[2]},
                "tracks": [t.__dict__ for t in g.tracks],
            } for g in groups
            ])
        print(f"Wrote JSON: {args.json}")

    if args.csv: 
        _write_csv(Path(args.csv), groups)
        print(f"Wrote CSV: {args.csv}")

    return 0

def cmd_delete(args) -> int: 

    client = SpotifyClient()
    items = list(client.iter_playlist_items(args.playlist, write=True))
    groups = group_duplicates(items, strict=args.strict, tol_secs=DEFAULT_TOLERANCE)

    num_duplicates = sum(len(group.tracks) for group in groups) - len(groups)
    print(f"Found {num_duplicates} Duplicate tracks in {len(groups)} Duplicate groups")

    payload = build_delete_payload(groups)
    if not payload.get("tracks"):
        print("Nothing to delete")
        return 0
    
    if not args.force: 
        print(json.dumps(payload, indent=2))
        response = input("Proceed to delete these occurrences? [y/N] ").strip().lower()
        if response != "y":
            print("Aborting deletion")
            return 1
    
    result = client.remove_tracks(args.playlist, payload)
    print("Delete request accepted.")
    print(json.dumps(result, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser: 
    p = argparse.ArgumentParser(prog="spotify-tools")
    sub = p.add_subparsers(dest="cmd", required=True)
    
    playlist_check = sub.add_parser("check", help="Scan a playlist and print/export duplicates")
    playlist_check.add_argument("--playlist", required=True)
    playlist_check.add_argument("--tol-secs", type=int, default=2)
    playlist_check.add_argument("--strict", action="store_true")
    playlist_check.add_argument("--json")
    playlist_check.add_argument("--csv")
    playlist_check.set_defaults(func=cmd_check)

    playlist_delete = sub.add_parser("delete", help="Remove duplicates (requires user token)")
    playlist_delete.add_argument("--playlist", required=True)
    playlist_delete.add_argument("--tol-secs", type=int, default=2)
    playlist_delete.add_argument("--strict", action="store_true")
    playlist_delete.add_argument("--force", action="store_true")
    playlist_delete.set_defaults(func=cmd_delete)

    return p

def main(argv: List[str] | None = None) -> int: 
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)

if __name__ == "__main__":
    raise SystemExit(main())
