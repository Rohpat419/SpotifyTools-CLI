# SpotifyTools - CLI App
Some tools that I thought would be useful for my Spotify experience that weren't built into the app. 

## Tools

- **Duplicate Cleaner**: Remove duplicate songs from your playlists.

This is surprisingly not a native spotify feature and was the first tool that I wanted to create for this project. The idea was first realized years ago in a super messy script. Now it exists as part of the semi-decent terminal app you see here. 


- **Explicit Content Filter**: Remove explicit content from your playlists.

This idea came to me when I was driving my little cousin home from school and I played my family friendly playlist. This playlist had 0 songs with the Spotify Explicit tag on it, but Hot N Cold by Katy Perry was in the playlist. This song is not marked as explicit on Spotify but it contains a curse word. I wanted a way to filter out explicit content based on lyrics. 


- **Top Artists/Tracks**: Get a list of your top artists or tracks.

I saw that the Spotify API has an endpoint for grabbing a user's top artists and tracks. I thought it would be a cool and easy feature to tack on to the app. People do like to see this kind of data (cough cough, Spotify Wrapped).


## How to Use


1. Clone the repository, set up Python environment:
   ```bash
    git clone https://github.com/Rohpat419/SpotifyTools-CLI.git
    cd SpotifyTools-CLI
    
    python -m venv .venv
    # On windows, allow scripts to run
    Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
    .\.venv\Scripts\activate # On macOS/Linux use `source .venv/bin/activate`
    pip install -e .
    ```
![Image showing cloning repo and cd into it](img/cloneCd.png)

![Image showing python env setup](img/pythonSetup.png)


2. Generate local certs for redirect URI:
 
 This is so your browser doesn't freak out when you authorize the app to access your Spotify account. The app needs this authorization to modify your playlists or read your top tracks/artists and private playlists.

   ```bash
    python -m spotify_tools.auth.make_dev_cert 
   ```

![Image showing cert generation](img/devCert.png)

This will create a localhost.pem and localhost-key.pem file in the root directory. 
&nbsp;

3. Fill out the environment variables in a .env file in the root directory:

Copy the .env.example file and fill in your SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET, you can get these by creating an app in the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/applications). 

Rename the copied file to `.env`. Like so: 

![Image showing .env file comparison to .env.example file](img/realEnvChange.png)

&nbsp;

4. Get a refresh token that will be used for modifying playlists or reading private data (top tracks/artists, private playlists). You will need to log in to your Spotify account and authorize the app to access your data.

    ```bash
    python -m spotify_tools.auth.server
    ```

Then ctrl+click the link in terminal or paste https://127.0.0.1:8080 into your browser. Login with Spotify on that page. 

![Image showing running auth server command](img/terminalServer.png)
![Image showing OAuth page](img/oAuthLogin.png)
This will create a `spotify_tokens.json` file in the root directory that will be used to authenticate requests.


&nbsp;

5. Run the application: 

    ```bash
    python -m spotify_tools.use_cli
    ```

Now feel free to explore the different features this app has to offer, the CLI will guide you through the rest!

![Image showing running the CLI command](img/openCLI.png)

## Next Steps: 
1. Make a frontend for the app. A terminal app is not the most user friendly. I can host the frontend to make the user experience easier than having them set up the environment. 
2. Convert the scripts into a real backend that can serve API requests. Then hook up the frontend to the backend. This backend needs to be hosted somewhere like render.com. 
3. Conduct a security review. Checking if tokens/keys are ever leaked. The refresh token is stored in plaintext on the user's computer which is already a flaw. This was considered OK since this is a dev POC typa project. 
