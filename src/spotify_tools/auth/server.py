# Spotify OAuth Demo Server (Authorization Code flow, no PKCE)
# Routes:
#   /login    -> redirect user to Spotify consent screen
#   /callback -> handle Spotify redirect, exchange code for tokens

from __future__ import annotations
import os, base64, json
from urllib.parse import urlencode

import requests
from flask import Flask, request, redirect, jsonify

from spotify_tools import config  # noqa

AUTH_URL  = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"

CLIENT_ID     = os.getenv("SPOTIFY_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")
REDIRECT_URI  = os.getenv("SPOTIFY_REDIRECT_URI", "https://127.0.0.1:8080/callback")
SCOPES        = os.getenv(
    "SPOTIFY_SCOPES",
    "playlist-modify-public playlist-modify-private playlist-read-private user-top-read",
)

app = Flask(__name__)


@app.get("/")
def index():
    html = f"""
    <html>
      <head>
        <title>Spotify OAuth Demo</title>
        <style>
          body {{
            font-family: Arial, sans-serif;
            background: radial-gradient(circle at top left, #1DB954 0%, #191414 80%);
            color: #fff;
            text-align: center;
            padding: 4rem;
          }}
          h1 {{
            margin-bottom: 1rem;
          }}
          a.button {{
            display: inline-block;
            padding: 0.75rem 1.5rem;
            margin-top: 1rem;
            background-color: #1DB954;
            color: #fff;
            border-radius: 4px;
            text-decoration: none;
            font-weight: bold;
            transition: background-color 0.2s ease;
          }}
          a.button:hover {{
            background-color: #17a44b;
          }}
          footer {{
            margin-top: 3rem;
            font-size: 0.8rem;
            color: #ccc;
          }}
        </style>
      </head>
      <body>
        <h1>Spotify OAuth Demo</h1>
        <p>This minimal server lets you log in with your Spotify account and fetch tokens.</p>
        <a class="button" href="/login">Login with Spotify</a>
        <footer>
          Redirect URI: {REDIRECT_URI}
        </footer>
      </body>
    </html>
    """
    return html



@app.get("/login")
def login():
    if not CLIENT_ID or not CLIENT_SECRET:
        return "Missing SPOTIFY_CLIENT_ID or SPOTIFY_CLIENT_SECRET in environment.", 500

    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
    }
    return redirect(f"{AUTH_URL}?{urlencode(params)}")


@app.get("/callback")
def callback():
    if (err := request.args.get("error")):
        return f"Spotify error: {err}", 400

    code = request.args.get("code")
    if not code:
        return "Missing 'code' in callback.", 400

    auth_b64 = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    headers = {"Authorization": f"Basic {auth_b64}"}
    data = {"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT_URI}
    r = requests.post(TOKEN_URL, headers=headers, data=data, timeout=30)
    if r.status_code != 200:
        return f"Token exchange failed: {r.status_code} {r.text}", 500

    tok = r.json()
    save_path = os.getenv("SPOTIFY_TOKEN_PATH", "spotify_tokens.json")
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(tok, f, indent=2)

    return jsonify(tok)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    cert = os.getenv("SSL_CERT")
    key  = os.getenv("SSL_KEY")

    if cert and key:
        app.run(host="127.0.0.1", port=port, ssl_context=(cert, key))
    else:
        try:
            app.run(host="127.0.0.1", port=port, ssl_context="adhoc")
        except Exception:
            app.run(host="127.0.0.1", port=port)
