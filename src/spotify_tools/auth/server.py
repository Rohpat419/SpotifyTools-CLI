# Minimal Spotify OAuth server (no PKCE)
# Routes:
#   /login    -> redirect user to Spotify consent
#   /callback -> receive ?code and exchange for tokens (using client secret)

from __future__ import annotations
import os, base64, json
from urllib.parse import urlencode
from flask import Flask, request, redirect, jsonify
from spotify_tools import config

import requests

AUTH_URL  = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"

# Read from environment (put these in your .env and load via your config if you like)
CLIENT_ID     = os.getenv("SPOTIFY_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")
REDIRECT_URI  = os.getenv("SPOTIFY_REDIRECT_URI", "https://localhost:8080/callback")
SCOPES        = os.getenv(
    "SPOTIFY_SCOPES",
    "playlist-modify-public playlist-modify-private playlist-read-private user-top-read",
)

app = Flask(__name__)
# For this minimal example we don’t need sessions; keep a secret just in case
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")


@app.get("/")
def index():
    print("Using cert:", os.getenv("SSL_CERT"))

    return (
        '<h1>Spotify OAuth (minimal)</h1>'
        '<p><a href="/login">Login with Spotify</a></p>'
    )


@app.get("/login")
def login():
    print("CLIENT_ID:", repr(CLIENT_ID))
    print("REDIRECT_URI:", repr(REDIRECT_URI))

    if not CLIENT_ID or not CLIENT_SECRET:
        return "Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in your environment.", 500

    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,  # must match what you registered
        "scope": SCOPES,
        # (Optional) you can add a state param if you want CSRF protection
        # "state": "any-string-you-like",
    }
    return redirect(f"{AUTH_URL}?{urlencode(params)}")


@app.get("/callback")
def callback():
    # Spotify may return an error, e.g., access_denied
    if (err := request.args.get("error")):
        return f"Spotify error: {err}", 400

    code = request.args.get("code")
    if not code:
        return "Missing 'code' in callback.", 400

    # Exchange code for tokens using client_id + client_secret (Basic auth)
    auth_b64 = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    headers = {"Authorization": f"Basic {auth_b64}"}
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }
    r = requests.post(TOKEN_URL, headers=headers, data=data, timeout=30)
    if r.status_code != 200:
        return f"Token exchange failed: {r.status_code} {r.text}", 500

    tok = r.json()
    # Optionally save tokens to a file for later use
    save_path = os.getenv("SPOTIFY_TOKEN_PATH", "spotify_tokens.json")
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(tok, f, indent=2)

    # Show the token payload (for debugging). In real use, don’t print secrets.
    return jsonify(tok)


if __name__ == "__main__":
    # HTTPS for local dev (recommended if the dashboard requires https redirects)
    port = int(os.getenv("PORT", "8080"))
    cert = os.getenv("SSL_CERT")
    key  = os.getenv("SSL_KEY")

    if cert and key:
        app.run(host="127.0.0.1", port=port, ssl_context=(cert, key))
    else:
        try:
            # Requires 'cryptography' to be installed for adhoc cert
            app.run(host="127.0.0.1", port=port, ssl_context="adhoc")
        except Exception:
            # Plain HTTP fallback (only works if your dashboard allows http://localhost redirects)
            exit()
            
            app.run(host="127.0.0.1", port=port)

