# scripts/get_user_token.py
# Obsolete until I want to implement PKCE for getting client secret for app 
import base64, hashlib, os, secrets, ssl, threading, urllib.parse, webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests

from spotify_tools.config import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET

CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "").strip()
REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "https://localhost:8080/callback")
SCOPES = "playlist-modify-public playlist-modify-private playlist-read-private user-top-read"

AUTH_URL  = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"

def _b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()

def make_pkce():
    verifier = _b64url(secrets.token_bytes(32))  # 43–128 chars
    challenge = _b64url(hashlib.sha256(verifier.encode()).digest())
    return verifier, challenge

class _Handler(BaseHTTPRequestHandler):
    code = None
    state_expected = None
    def do_GET(self):
        qs = urllib.parse.urlparse(self.path)
        params = dict(urllib.parse.parse_qsl(qs.query))
        if qs.path == urllib.parse.urlsplit(REDIRECT_URI).path and "code" in params:
            if params.get("state") != self.state_expected:
                self.send_response(400); self.end_headers()
                self.wfile.write(b"State mismatch"); return
            _Handler.code = params["code"]
            self.send_response(200); self.end_headers()
            self.wfile.write(b"You can close this window.")
        else:
            self.send_response(404); self.end_headers()

def main():
    assert CLIENT_ID, "Set SPOTIFY_CLIENT_ID in your .env"
    verifier, challenge = make_pkce()
    state = _b64url(secrets.token_bytes(16))

    # tiny local server to catch the redirect
    host, port = urllib.parse.urlsplit(REDIRECT_URI).netloc.split(":")
    server = HTTPServer((host, int(port)), _Handler)
    
    # Add SSL support for HTTPS
    if REDIRECT_URI.startswith('https://'):
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        # Use the existing certificate files in your project
        context.load_cert_chain('localhost.pem', 'localhost-key.pem')
        server.socket = context.wrap_socket(server.socket, server_side=True)
    
    _Handler.state_expected = state
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()

    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "code_challenge_method": "S256",
        "code_challenge": challenge,
        "state": state,
        "show_dialog": "true",
    }
    url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"
    print("Opening browser for Spotify consent…")
    webbrowser.open(url)

    # wait for code
    print("Waiting for redirect with authorization code…")
    while _Handler.code is None:
        pass
    server.shutdown()

    # exchange code for tokens
    data = {
        "grant_type": "authorization_code",
        "code": _Handler.code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "code_verifier": verifier,
    }
    r = requests.post(TOKEN_URL, data=data, timeout=30)
    r.raise_for_status()
    tok = r.json()
    print("\nACCESS TOKEN (expires ~1h):\n", tok["access_token"])
    print("\nREFRESH TOKEN:\n", tok["refresh_token"])
    print("\nEXPIRES IN (seconds):", tok.get("expires_in"))
    print("\nNext: put this in your .env -> SPOTIFY_REFRESH_TOKEN=...")

if __name__ == "__main__":
    main()
