# src/spotify_tools/auth/user_token.py
from __future__ import annotations
import base64, os, time, requests

TOKEN_URL = "https://accounts.spotify.com/api/token"

# import your env loader so .env is read automatically
from spotify_tools import config  # noqa: F401

CLIENT_ID     = os.getenv("SPOTIFY_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")
REFRESH_TOKEN = os.getenv("SPOTIFY_REFRESH_TOKEN", "")

_TOKEN_CACHE = {"access": None, "exp": 0}  # simple in-process cache

def get_user_access_token() -> str:
    """Return a valid user access token (refreshing if needed)."""
    now = time.time()
    if _TOKEN_CACHE["access"] and now < _TOKEN_CACHE["exp"] - 30:
        return _TOKEN_CACHE["access"]

    assert CLIENT_ID and CLIENT_SECRET and REFRESH_TOKEN, "Missing CLIENT_ID/SECRET/REFRESH_TOKEN"

    basic = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    headers = {"Authorization": f"Basic {basic}"}
    data = {"grant_type": "refresh_token", "refresh_token": REFRESH_TOKEN}
    r = requests.post(TOKEN_URL, headers=headers, data=data, timeout=30)
    r.raise_for_status()
    tok = r.json()

    access = tok["access_token"]
    ttl    = int(tok.get("expires_in", 3600))

    # NOTE: Spotify may sometimes return a *new* refresh_token; persist it if you want rotation.
    # new_refresh = tok.get("refresh_token")

    _TOKEN_CACHE["access"] = access
    _TOKEN_CACHE["exp"] = now + ttl
    return access
