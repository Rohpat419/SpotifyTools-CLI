# SpotifyTools
Some tools that I thought would be useful for my Spotify experience that weren't built into the app. 

## Features

- **Duplicate Cleaner**: Remove duplicate songs from your playlists.

This is not a native spotify feature and was the first tool that I wanted to create for this project. The idea was first realized years ago in a super messy script. Now it exists as part of the semi-decent terminal app you see here. 



- **Explicit Content Filter**: Remove explicit content from your playlists.


- **Top Artists/Tracks**: Get a list of your top artists or tracks.



## How to Use


1. Clone the repository, set up Python environment:
   ```bash
    git clone https://github.com/Rohpat419/SpotifyTools-CLI.git
    cd SpotifyTools-CLI
    
    python -m venv .venv
    On Windows use `.venv\Scripts\activate` # On macOS/Linux use `source .venv/bin/activate`
    pip install -r requirements.txt
    ```

2. Generate local certs for redirect URI so your browser doesn't freak out when you authorize the app to access your Spotify account. The app needs this authorization to modify your playlists or read your top tracks/artists and private playlists.

   ```bash
    python -m spotify_tools.auth.make_dev_cert 
   ```

    This will create a localhost.pem and localhost-key.pem file in the root directory. 
&nbsp;
3. Fill out the environment variables in a .env file in the root directory. 
Copy the .env.example file and fill in your SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET, you can get these by creating an app in the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/applications). Make sure to set the Redirect URI to `https://127.0.0.1:8080/callback` in your app settings. 

Rename the copied file to `.env`.
&nbsp;
4. Get a refresh token that will be used for modifying playlists or reading private data (top tracks/artists, private playlists). You will need to log in to your Spotify account and authorize the app to access your data.

    ```bash
    python -m spotify_tools.auth.server
    ```

This will create a `spotify_tokens.json` file in the root directory that will be used to authenticate requests.
&nbsp;

5. Run the application: 

    ```bash
    python -m spotify_tools.cli
    ```

Now feel free to explore the different features this app has to offer, the CLI will guide you through the rest!