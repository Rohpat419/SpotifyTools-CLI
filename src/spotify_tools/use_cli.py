# Run the cli version of the app, meant to be replaced by the web app
import argparse, csv, json
from pathlib import Path
from typing import Any, Dict, List

from .client import SpotifyClient
from .duplicates import group_duplicates, DEFAULT_TOLERANCE
from .explicit import interactive_run as explicit_interactive
from .tops import interactive_run as tops_interactive

from . import config
import requests

import time

PAUSE_SECS = 0.5

def _ui_pause():
    time.sleep(PAUSE_SECS)

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

# Only used in cmd_delete to check for duplicates ahead of time
def _scan_duplicates(client: SpotifyClient, playlist: str, strict: bool, tol_secs: int):
    """Return (groups, num_duplicates, items) for reuse in check/delete flows."""
    items = list(client.iter_playlist_items(playlist, write=True))  # user token so private playlists work
    groups = group_duplicates(items, strict=strict, tol_secs=tol_secs)
    num_duplicates = sum(len(g.tracks) for g in groups) - len(groups)
    return groups, num_duplicates, items


def cmd_check(args) -> int: 
    client = SpotifyClient()
    try: 
        items = list(client.iter_playlist_items(args.playlist, write=False))
    except requests.HTTPError as e:
        status = getattr(e.response, "status_code", None) 
        if status in (401, 404): 
            print("Playlist may be private or restricted; retrying with user auth...")
            items = list(client.iter_playlist_items(args.playlist, write=True))
            print("User auth succeeded, continuing...")
        else: 
            raise

    groups = group_duplicates(items, strict=args.strict, tol_secs=args.tol_secs)

    # total number of duplicates is the number of tracks in all the groups - number of groups since each group has 1 non-duplicate
    num_duplicates = sum(len(group.tracks) for group in groups) - len(groups)
    print(f"\nFound {num_duplicates} Duplicate tracks in {len(groups)} Duplicate groups")


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

def _chunk(lst, n=100): 
    for i in range(0, len(lst), 100): 
        yield lst[i:i+n]

def cmd_delete(args) -> int: 

    client = SpotifyClient()
    items = list(client.iter_playlist_items(args.playlist, write=True))
    groups = group_duplicates(items, strict=args.strict, tol_secs=DEFAULT_TOLERANCE)

    num_duplicates = sum(len(group.tracks) for group in groups) - len(groups)
    print(f"Found {num_duplicates} Duplicate tracks in {len(groups)} Duplicate groups")

    if num_duplicates <= 0: 
        print("Nothing to delete")
        return 0

    if not args.force:
        confirm = input("Proceed to wipe duplicate URIs and re-add one keeper per group? [y/N]: ").strip().lower()
        if confirm != "y":
            print("Aborting deletion")
            return 1
        
    result = client.clear_dupes_then_readd(
        args.playlist, strict=args.strict, tol_secs=args.tol_secs
    )

    print("Delete request accepted.")
    print(json.dumps(result, indent=2))
    print(f"Done. Kept {result['kept']} tracks, removed {result['removed']} (from {result['original']}).")
    return 0


def build_parser() -> argparse.ArgumentParser: 
    p = argparse.ArgumentParser(prog="spotify-tools")
    # if running without subcommand, default to interactive menu
    sub = p.add_subparsers(dest="cmd", required=False)
    

    playlist_check = sub.add_parser("check", help="Scan a playlist and print/export duplicates")
    playlist_check.add_argument("--playlist", required=True)
    playlist_check.add_argument("--tol-secs", type=int, default=DEFAULT_TOLERANCE)
    playlist_check.add_argument("--strict", action="store_true")
    playlist_check.add_argument("--json")
    playlist_check.add_argument("--csv")
    playlist_check.set_defaults(func=cmd_check)

    playlist_delete = sub.add_parser("delete", help="Remove duplicates (requires user token)")
    playlist_delete.add_argument("--playlist", required=True)
    playlist_delete.add_argument("--tol-secs", type=int, default=DEFAULT_TOLERANCE)
    playlist_delete.add_argument("--strict", action="store_true")
    playlist_delete.add_argument("--force", action="store_true", help="Do not prompt for confirmation")
    playlist_delete.set_defaults(func=cmd_delete)

    p.add_argument("-i", "--interactive", action="store_true", help="Use interactive menu if present")
    
    return p

def interactive_menu() -> None:
    client = SpotifyClient()
    while True:
        _ui_pause()
        print("\n=== Spotify Tools ===")
        print("1) Scan playlist for duplicates")
        print("2) Delete playlist duplicates")
        print("3) Explicit content filter (based on Explicit flag or lyrics)")
        print("4) See my Top 5 (tracks/artists)")
        print("0) Exit")
        choice = input("Choose an option: ").strip()

        if choice == "1":
            playlist = input("Playlist URL or ID: ").strip()
            # if user is in interactive mode they're here for an easy time, don't introduce strict option
            # strict = input("Strict title matching?  [y/N]: ").strip().lower() == "y"
            # same use case for duration tolerance, 2 second default is fine
            # tol = input(f"Duration tolerance in seconds [{DEFAULT_TOLERANCE}]: ").strip()
            tol_secs = DEFAULT_TOLERANCE
            args = type("Args", (), {"playlist": playlist, "strict": False, "tol_secs": tol_secs, "json": None, "csv": None})
            _ui_pause()

            cmd_check(args)

        elif choice == "2":
            playlist = input("Playlist URL or ID: ").strip()
            # strict = input("Strict title matching? [y/N]: ").strip().lower() == "y"
            # tol = input(f"Duration tolerance in seconds [{DEFAULT_TOLERANCE}]: ").strip()
            tol_secs = DEFAULT_TOLERANCE

            # Show a duplicate summary first
            groups, num_duplicates, _items = _scan_duplicates(SpotifyClient(), playlist, False, tol_secs)
            if num_duplicates <= 0:
                print("No duplicates found, nothing to delete.")
                continue
            else: 
                print("\nDuplicates found: ")
                for idx, g in enumerate(groups, 1):
                    names = {t.name for t in g.tracks}
                    artists = {", ".join(t.artists) for t in g.tracks}
                    print(f"[{idx}] {list(names)[0]} — {list(artists)[0]}  (x{len(g.tracks)})")
            
            
            force = input("\nSkip confirmation and delete now? [y/N]: ").strip().lower() == "y"
            args = type("Args", (), {"playlist": playlist, "strict": False, "tol_secs": tol_secs, "force": force})
            _ui_pause()
            cmd_delete(args)

        elif choice == "3":
            _ui_pause()
            explicit_interactive(client)

        elif choice == "4":
            _ui_pause()
            tops_interactive(client)

        elif choice == "0":
            print("Thanks for using the app!")
            return
        else:
            print("Invalid choice, try again.")


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # If user inputted interactive mode or did NOT put in cmd mode, go to interactive mode
    if getattr(args, "interactive", False) or not getattr(args, "cmd", None):
        interactive_menu()
        return 0
    
    return args.func(args)



if __name__ == "__main__":
    raise SystemExit(main())
