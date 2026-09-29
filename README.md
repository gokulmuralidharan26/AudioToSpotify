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
- Not yet tested against live YouTube/TikTok in this repo's dev environment; unit
  tests cover URL validation, filename sanitising and auth.
