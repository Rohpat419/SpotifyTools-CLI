# src/spotify_tools/auth/user_token.py
from __future__ import annotations
import base64, os, time, requests
from pathlib import Path
import json

TOKEN_URL = "https://accounts.spotify.com/api/token"

# import your env loader so .env is read automatically
from spotify_tools import config  # noqa: F401

CLIENT_ID     = os.getenv("SPOTIFY_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")

# Always resolve token path relative to project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]   # up to repo root
TOKEN_PATH   = Path(os.getenv("SPOTIFY_TOKEN_PATH", PROJECT_ROOT / "spotify_tokens.json"))


_TOKEN_CACHE = {"access": None, "exp": 0}  # simple in-process cache

def _load_refresh_token() -> str:
    """Read the refresh token from spotify_tokens.json at the project root."""
    try:
        with open(TOKEN_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            rtok = data.get("refresh_token")
            if not rtok:
                raise RuntimeError(f"No refresh_token found in {TOKEN_PATH}")
            return rtok
    except FileNotFoundError:
        raise RuntimeError(f"Token file {TOKEN_PATH} not found. Run auth flow first.")


def _save_refresh_token(new_refresh: str) -> None:
    """Persist a new refresh token if Spotify rotates it."""
    try:
        with open(TOKEN_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {}
    data["refresh_token"] = new_refresh
    with open(TOKEN_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def get_user_access_token() -> str:
    """Return a valid user access token (refreshing if needed)."""
    now = time.time()
    if _TOKEN_CACHE["access"] and now < _TOKEN_CACHE["exp"] - 30:
        return _TOKEN_CACHE["access"]

    assert CLIENT_ID and CLIENT_SECRET, "Missing CLIENT_ID or CLIENT_SECRET"
    refresh_token = _load_refresh_token()

    basic = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    headers = {"Authorization": f"Basic {basic}"}
    data = {"grant_type": "refresh_token", "refresh_token": refresh_token}
    r = requests.post(TOKEN_URL, headers=headers, data=data, timeout=30)
    r.raise_for_status()
    tok = r.json()

    access = tok["access_token"]
    ttl    = int(tok.get("expires_in", 3600))

    # Spotify may sometimes return a new refresh token
    if "refresh_token" in tok:
        _save_refresh_token(tok["refresh_token"])

    _TOKEN_CACHE["access"] = access
    _TOKEN_CACHE["exp"] = now + ttl
    return access
