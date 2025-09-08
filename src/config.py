# config.py (import this early in your app)
import os
from dotenv import load_dotenv, find_dotenv

# Loads ${workspace}/.env if present; doesn't overwrite existing env by default
load_dotenv(find_dotenv(), override=False)

SPOTIFY_CLIENT_ID    = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET= os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_USER_TOKEN   = os.getenv("SPOTIFY_USER_TOKEN")
