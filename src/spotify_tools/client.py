# This file handles the networking between Spotify servers and the user (client). Including Auth

from __future__ import annotations
import os
import time
import urllib.parse as up
from typing import Dict, Generator, List, Optional
import requests

from spotify_tools.auth.user_token_from_refresh import get_user_access_token
from spotify_tools.duplicates import compute_keep_and_delete_uris

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
        if write:
            token = get_user_access_token()
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
        
        print("Playlist ID not filtered by parser, either correct ID given or the parser was skipped accidentally")        
        return input


    def iter_playlist_items(self, playlist_id: str, *, write: bool = False):
        pid = self.playlist_id_from_input(playlist_id)
        headers = self._auth_header(write=write)

        url = f"{API_URL}/playlists/{pid}/tracks"
        params = {"limit": 100}

        retry_counter = 0
        while True and retry_counter < 10:
            r = requests.get(url, headers=headers, params=params, timeout=TIMEOUT)
            retry_counter += 1
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
    
    # Deletes all songs that are identified as duplicate, too destructive
    # def remove_tracks(self, playlist_url: str, deletion_payload: dict) -> dict: 
    #     playlist_id = self.playlist_id_from_input(playlist_url)
    #     headers = self._auth_header(write=True)
    #     headers.update({"Content-Type": "application/json"})
    #     r = requests.delete(f"{API_URL}/playlists/{playlist_id}/tracks",
    #                         headers=headers, json=deletion_payload, timeout=TIMEOUT)
    #     r.raise_for_status()
    #     return r.json()
        

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
    
    def remove_by_uri(self, playlist_id: str, uris: List[str]) -> None: 
        pid = self.playlist_id_from_input(playlist_id)
        headers = self._auth_header(write=True)
        headers.update({"Content-Type": "application/json"})

        seen = set()
        unique = []
        for u in uris: 
            if u and u not in seen: 
                seen.add(u)
                unique.append(u)
        # maxes out at 100 per call
        for i in range(0, len(unique), 100):
            chunk = unique[i:i+100]
            payload = {"tracks": [{"uri": u} for u in chunk]} 
            r = requests.delete(f"{API_URL}/playlists/{pid}/tracks",
                    headers=headers, json=payload, timeout=TIMEOUT)
            r.raise_for_status()

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
    
    def clear_dupes_then_readd(self, playlist_id: str, *, strict: bool = False, tol_secs: int = 2) -> dict:
        """
        Read the playlist
        Build (keep_uris, delete_uris)
        Delete all delete_uris
        Add back keep_uris
        """
        
        items = list(self.iter_playlist_items(playlist_id, write=True))
        original_count = sum(1 for it in items if (it.get("track") or {}).get("type") == "track")

        keep_uris, delete_uris = compute_keep_and_delete_uris(items, strict=strict, tol_secs=tol_secs)

        if delete_uris: 
            self.remove_by_uri(playlist_id, delete_uris)
        
        if keep_uris: 
            self.add_items(playlist_id, keep_uris)
        
        return {"original": original_count, "kept": len(keep_uris), "removed": len(delete_uris)}

    def create_playlist(self, user_id: str, name: str, description: str = "", public: bool = False) -> str: 
        """
        Create a new playlist under the given user account.
        Returns the new playlist ID.
        """
        headers = self._auth_header(write=True)
        headers.update({"Content-Type": "application/json"})
        body = {
            "name": name,
            "description": description,
            "public": public,
        }
        r = requests.post(f"{API_URL}/users/{user_id}/playlists",
                          headers=headers, json=body, timeout=30)
        r.raise_for_status()
        return r.json()["id"]

    def get_current_user_id(self) -> str:
        headers = self._auth_header(write=True)
        r = requests.get(f"{API_URL}/me", headers=headers, timeout=30)
        r.raise_for_status()
        return r.json()["id"]
    
    def playlist_name_from_id(self, playlist_id: str, write: bool) -> str: 
        headers=self._auth_header(write=write)
        pid = self.playlist_id_from_input(playlist_id)

        url = f"{API_URL}/playlists/{pid}"

        retry_counter = 0
        while True and retry_counter < 5: 
            r = requests.get(url, headers=headers, timeout=TIMEOUT)
            retry_counter += 1
            if r.status_code == 429: 
                retry_timer = int(r.headers.get("Retry-After", "1"))
                time.sleep(retry_timer)
                continue
            retry_counter += 1
            try: 
                r.raise_for_status()
            except requests.HTTPError as e:
                status = getattr(e.response, "status_code", None)
                if status in (401, 404) and not write:
                    print("Playlist may be private or restricted; retrying with user auth...")
                    headers = self._auth_header(write=True)
                    # loop will retry with new headers
                    continue
                else:
                    raise

            data = r.json()
            
            if data.get("name"): 
                return data["name"]
            else: 
                print("Could not find the name of the original playlist, defaulting to Nothing")
                return ""
            
