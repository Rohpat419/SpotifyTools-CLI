# This file handles the networking between Spotify servers and the user (client). Including Auth

from __future__ import annotations
import os
import time
import urllib.parse as up
from typing import Dict, Generator, List, Optional
import requests

TIMEOUT=30

API_URL = "https://api.spotify.com/v1"

class SpotifyClient: 
    def __init__(self, *, client_id: Optional[str] = None, client_secret: Optional[str] = None, user_token: Optional[str] = None):
        self.client_id = client_id or os.getenv("SPOTIFY_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("SPOTIFY_CLIENT_SECRET")
        self.user_token = user_token or os.getenv("SPOTIFY_USER_TOKEN")

        # Not user supplied, client needs to cache app token from Spotify servers
        self._app_token : Optional[str] = None

    def _get_app_token(self) -> str:
        if self._app_token: 
            return self._app_token
        if not (self.client_id and self.client_secret):
            raise RuntimeError("Missing client credentials.")
        r = requests.post(
            "https://accounts.spotify.com/api/token",
            data={"grant_type": "client_credentials"},
            auth=(self.client_id, self.client_secret),
            timeout=TIMEOUT
        )
        r.raise_for_status()
        self._app_token = r.json()["access_token"]
        return self._app_token
    
    # auth token is either user token if doing a write to playlist or it's been supplied, handy for private playlist reads. ELSE use the app token for basic reads. 
    def _auth_header(self, write: bool) -> Dict[str, str]:
        
        if write or self.user_token: 
            token = self.user_token
        else: 
            token = self._get_app_token()
        # token = self.user_token if write or self.user_token else self._get_app_token()
        return {"Authorization": f"Bearer {token}"}
    
    # COME BACK TO THIS, should I enforce https right here?
    @staticmethod
    def playlist_id_from_input(input: str) -> str: 
        if input.startswith("http"):
            parsed = up.urlparse(input)
            # Remove trailing / then split the url based on / . This prevents the final string from being ""
            parts = parsed.path.strip("/").split("/")
            if len(parts) >= 2 and parts[-2] == "playlist":
                return parts[-1]
        
        print("Playlist ID not parsed by parser, I hope you know what you're doing")        
        return input
    
    def iter_playlist_items(self, playlist_id: str, *, write: bool = False):
        pid = self.playlist_id_from_input(playlist_id)
        headers = self._auth_header(write=write)

        url = f"{API_URL}/playlists/{pid}/tracks"
        params = {"limit": 100}

        while True:
            r = requests.get(url, headers=headers, params=params, timeout=TIMEOUT)
            if r.status_code == 429:
                retry_timer = int(r.headers.get("Retry-After", "1"))
                time.sleep(retry_timer)
                continue
            r.raise_for_status()
            data = r.json()
            for item in data.get("items", []):
                yield item
            url = data.get("next")
            if not url:
                break

    def remove_tracks(self, playlist_url: str, deletion_payload: dict) -> dict: 
        playlist_id = self.playlist_id_from_input(playlist_url)
        headers = self._auth_header(write=True)
        headers.update({"Content-Type": "application/json"})
        r = requests.delete(f"{API_URL}/playlists/{playlist_id}/tracks",
                            headers=headers, json=deletion_payload, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
        

    # OPTIONAL LOGIC: replaces items. Not a big fan of this idea
    def replace_items(self, playlist_id: str, uris: List[str]) -> dict:
        """Replace the playlist's items with up to 100 URIs."""
        if len(uris) > 100:
            raise ValueError("replace_items accepts at most 100 URIs")
        pid = self.playlist_id_from_input(playlist_id)
        headers = self._auth_header(write=True)
        headers.update({"Content-Type": "application/json"})
        r = requests.put(f"{API_URL}/playlists/{pid}/tracks",
                        headers=headers, json={"uris": uris}, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    
    def add_items(self, playlist_id: str, uris: List[str], position: Optional[int] = None) -> dict:
        """Append up to 100 URIs (or insert at a position)."""
        if len(uris) > 100:
            raise ValueError("add_items accepts at most 100 URIs")
        pid = self.playlist_id_from_input(playlist_id)
        headers = self._auth_header(write=True)
        headers.update({"Content-Type": "application/json"})
        body = {"uris": uris}
        if position is not None:
            body["position"] = int(position)
        r = requests.post(f"{API_URL}/playlists/{pid}/tracks",
                        headers=headers, json=body, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    
