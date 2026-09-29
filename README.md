# AudioToSpotify

Paste (or share) a YouTube / TikTok link → get a tagged MP3 saved straight into
your iPhone's Spotify folder. No manual download-and-move.

```
iPhone Share Sheet ──URL──▶ Shortcut ──POST /convert──▶ this server (yt-dlp + ffmpeg)
                                │                                   │
                                └──────── MP3 (title/artist/art) ◀──┘
                                │
                                └─▶ Save File → Files › On My iPhone › Spotify
```

## 1. Run the server

Needs Python 3.11+ and `ffmpeg`. Easiest is Docker (works on a Mac/PC/Raspberry Pi
at home, or any small VPS / Fly.io / Railway):

```bash
docker build -t audiotospotify .
docker run -d -p 8080:8080 -e A2S_TOKEN=$(openssl rand -hex 24) --restart unless-stopped audiotospotify
```

Or without Docker: `pip install -r requirements.txt && A2S_TOKEN=yoursecret python app.py`.

Reach it from your phone via the same Wi-Fi (`http://<computer-ip>:8080`), or from
anywhere with [Tailscale](https://tailscale.com) (recommended: private, free, no
port-forwarding) or a hosted deployment with HTTPS. Keep `A2S_TOKEN` secret; the
server also only accepts YouTube/TikTok URLs.

Quick test: `python cli.py "https://youtu.be/..."` saves an MP3 locally.

## 2. Build the iOS Shortcut (one-time, ~2 min)

Shortcuts app → **+** → name it **Send to Spotify**, then in its settings enable
**Show in Share Sheet** (accept *URLs*). Add these actions:

1. **Get Contents of URL**
   - URL: `http://<server>:8080/convert`
   - Method: **POST**
   - Headers: `Authorization` = `Bearer <your A2S_TOKEN>`
   - Request Body: **JSON**, field `url` (Text) = *Shortcut Input*
2. **Save File**
   - Turn off *Ask Where to Save*, choose **On My iPhone › Spotify**
     (or pick the folder yourself the first time), *Overwrite* off.
3. *(optional)* **Show Notification** "Saved to Spotify".

Now in YouTube/TikTok: **Share → Send to Spotify**. Also works by copying a link and
running the shortcut from the home screen or Siri (use *Get Clipboard* in place of
Shortcut Input).

## Free, no-server option: GitHub Actions

No computer or extra app needed. The Shortcut triggers `.github/workflows/convert.yml`
in this repo; GitHub converts the link and publishes the MP3 as a release named
`latest`; the Shortcut downloads it and saves it to your Spotify folder. Takes ~1 min.

**Setup**
1. Keep this repo **private** (the MP3s land in its releases). Private repos get
   2,000 free Actions minutes/month, roughly 1,000+ songs.
2. Create a fine-grained token at GitHub → Settings → Developer settings → Personal
   access tokens, limited to this repo, with **Actions: Read and write** and
   **Contents: Read-only**.
3. *(YouTube only, if it says "Sign in to confirm you're not a bot")* export your
   YouTube cookies (Netscape format, e.g. the "Get cookies.txt LOCALLY" browser
   extension) and save them as a repo secret named `YT_COOKIES`.
4. Merge this branch to the default branch so the workflow is available there.

**Shortcut** ("Send to Spotify", enabled in Share Sheet for URLs). Replace
`OWNER/REPO` and `TOKEN`; every request also needs the headers
`Authorization: Bearer TOKEN` and `Accept: application/vnd.github+json`.
1. **Current Date** → format as *Custom* `yyyyMMddHHmmss` → this is the request id.
2. **Get Contents of URL**: POST `https://api.github.com/repos/OWNER/REPO/actions/workflows/convert.yml/dispatches`,
   body JSON: `ref` = `main` (your default branch), `inputs` = dictionary with
   `url` = Shortcut Input and `request_id` = the request id.
3. **Wait** 60 seconds (raise it if conversions take longer).
4. **Get Contents of URL**: GET `https://api.github.com/repos/OWNER/REPO/releases/tags/latest`
5. **Get Dictionary Value** `body`; **If** it isn't the request id, **Show Alert**
   "Not ready yet, run again in a bit" and stop.
6. **Get Dictionary Value** `assets` → **First Item** → keys `url` and `name`.
7. **Get Contents of URL**: GET that asset `url` with header
   `Accept: application/octet-stream` (plus the Authorization header).
8. **Save File** with name = asset `name`, into On My iPhone › Spotify.

## Caveats

- **Spotify's local-files support on iOS is limited.** Spotify's official flow is
  desktop-based: add files to a folder Spotify Desktop watches, put them in a
  playlist, then download that playlist on the phone over the same Wi-Fi. Since you
  already have a phone-side folder that works, this tool targets it; if that ever
  stops working, the fallback is to point the server's output at your desktop's
  local-files folder (`python cli.py <url> ~/Music/Spotify-Local`).
- Local files must be MP3/M4A/MP4 and show up under *Your Library → Local Files*
  (enable *Settings → Local Files* first). Title/artist tags are embedded so they
  display properly.
- Downloading may violate YouTube/TikTok terms and copyright; use for content you're
  entitled to. Keep `yt-dlp` updated (`pip install -U yt-dlp`) — sites change often.
- Tested end to end via GitHub Actions: a TikTok *sound* link (`tiktok.com/t/...`)
  converts to a tagged MP3 and is published as the `latest` release. YouTube from
  GitHub's servers is blocked without cookies (see setup step 3) and is untested with them.
- Set `A2S_DEBUG=1` on the Convert step to get verbose yt-dlp / TikTok page diagnostics.
