"""Download audio from a YouTube/TikTok link and convert it to a tagged MP3."""
import os
import json
import re
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import requests
import yt_dlp

ALLOWED_HOSTS = (
    "youtube.com", "youtu.be", "music.youtube.com",
    "tiktok.com", "vm.tiktok.com", "vt.tiktok.com",
)


class ConversionError(Exception):
    pass


def validate_url(url: str) -> str:
    url = url.strip()
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in ("http", "https") or not any(
        host == h or host.endswith("." + h) for h in ALLOWED_HOSTS
    ):
        raise ConversionError("Only YouTube and TikTok links are supported.")
    return url


def safe_filename(name: str) -> str:
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "", name).strip(" .")
    return (name or "audio")[:120]


BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)


IPHONE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1"
)


def _meta(html: str) -> dict:
    return {
        k: v for k, v in re.findall(
            r'<meta[^>]+(?:property|name)="([^"]+)"[^>]+content="([^"]*)"', html)
    }


def _is_youtube(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == h or host.endswith("." + h) for h in ("youtube.com", "youtu.be"))


def _convert_cobalt(url: str, out_dir: Path) -> Path:
    """Ask a Cobalt API instance (COBALT_API_URL, optional COBALT_API_KEY) for an MP3."""
    api = os.environ["COBALT_API_URL"].rstrip("/")
    headers = {"Accept": "application/json", "Content-Type": "application/json",
               "User-Agent": "AudioToSpotify/1.0"}
    if os.environ.get("COBALT_API_KEY"):
        headers["Authorization"] = f"Api-Key {os.environ['COBALT_API_KEY']}"
    try:
        r = requests.post(
            api + "/",
            json={"url": url, "downloadMode": "audio", "audioFormat": "mp3", "audioBitrate": "192"},
            headers=headers, timeout=60,
        )
        data = r.json()
    except (requests.RequestException, ValueError) as e:
        raise ConversionError(f"Cobalt request failed: {e}") from e
    if data.get("status") not in ("tunnel", "redirect") or not str(data.get("url", "")).startswith("https://"):
        err = data.get("error", {})
        code = err.get("code") if isinstance(err, dict) else err
        raise ConversionError(f"Cobalt refused: {data.get('status')} {code} (HTTP {r.status_code})")
    name = safe_filename(Path(data.get("filename") or "audio.mp3").stem) + ".mp3"
    final = out_dir / name
    try:
        with requests.get(data["url"], headers={"User-Agent": "AudioToSpotify/1.0"},
                          stream=True, timeout=120) as dl:
            dl.raise_for_status()
            with open(final, "wb") as f:
                for chunk in dl.iter_content(1 << 16):
                    f.write(chunk)
    except requests.RequestException as e:
        raise ConversionError(f"Cobalt download failed: {e}") from e
    if final.stat().st_size < 10_000:
        raise ConversionError("Cobalt returned an empty or truncated file.")
    return final


def _find_music(obj):
    """Depth-first search for the TikTok sound dict (has playUrl + title)."""
    if isinstance(obj, dict):
        if isinstance(obj.get("playUrl"), str) and obj.get("title"):
            return obj
        obj = list(obj.values())
    if isinstance(obj, list):
        for v in obj:
            found = _find_music(v)
            if found:
                return found
    return None


def _key_paths(obj, prefix="", depth=0, out=None):
    """Structure-only summary (keys, no values) used to diagnose page layout changes."""
    out = [] if out is None else out
    if depth > 6 or len(out) > 150:
        return out
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.append(f"{prefix}.{k}" + ("" if isinstance(v, (dict, list)) else f"<{type(v).__name__}>"))
            _key_paths(v, f"{prefix}.{k}", depth + 1, out)
    elif isinstance(obj, list) and obj:
        _key_paths(obj[0], prefix + "[0]", depth + 1, out)
    return out


def _convert_tiktok_sound(page_url: str, html: str, out_dir: Path) -> Path:
    """yt-dlp can't extract TikTok *sound* pages, so read the audio URL from the page."""
    m = re.search(
        r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>', html, re.S
    )
    if not m:
        raise ConversionError("TikTok sound page had no embedded data (blocked or changed).")
    data = json.loads(m.group(1))
    music = _find_music(data)
    if not music:
        meta = _meta(html)
        audio = meta.get("og:audio:secure_url") or meta.get("og:audio")
        if audio and meta.get("og:title"):
            music = {"playUrl": audio, "title": meta["og:title"], "authorName": None}
    if not music:
        detail = ""
        if os.environ.get("A2S_DEBUG"):
            scope = data.get("__DEFAULT_SCOPE__", data)
            ctx = scope.get("webapp.app-context", {})
            detail = (f"len={len(html)} botType={ctx.get('botType')} scopes={list(scope)} "
                      f"ldjson={'application/ld+json' in html} "
                      f"meta={ {k: v[:80] for k, v in _meta(html).items()} }")
        raise ConversionError(f"Could not find the audio URL on the TikTok sound page. {detail}")
    play_url = music["playUrl"]
    if not play_url.startswith("https://"):
        raise ConversionError("Unexpected TikTok audio URL.")
    src = out_dir / "sound.src"
    with requests.get(play_url, headers={"User-Agent": BROWSER_UA, "Referer": page_url},
                      stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(src, "wb") as f:
            for chunk in r.iter_content(1 << 16):
                f.write(chunk)
    title = music["title"]
    artist = music.get("authorName") or "TikTok"
    final = out_dir / (safe_filename(f"{artist} - {title}") + ".mp3")
    proc = subprocess.run(
        ["ffmpeg", "-y", "-i", str(src), "-vn", "-codec:a", "libmp3lame", "-b:a", "192k",
         "-metadata", f"title={title}", "-metadata", f"artist={artist}", str(final)],
        capture_output=True, text=True,
    )
    if proc.returncode != 0 or not final.exists():
        raise ConversionError(f"ffmpeg failed: {proc.stderr[-300:]}")
    return final


def convert(url: str, out_dir: Path | None = None) -> Path:
    """Download `url` and return the path of the resulting .mp3 file."""
    url = validate_url(url)
    out_dir = Path(out_dir or tempfile.mkdtemp(prefix="a2s_"))
    cobalt_error = None
    if _is_youtube(url) and os.environ.get("COBALT_API_URL"):
        try:
            return _convert_cobalt(url, out_dir)
        except ConversionError as e:
            cobalt_error = str(e)
            print(f"{e}; falling back to yt-dlp")
    if "tiktok.com" in url:
        try:
            # TikTok only serves the sound data to mobile browsers (verified from GitHub's IPs).
            page = requests.get(url, headers={"User-Agent": IPHONE_UA}, timeout=30)
        except requests.RequestException as e:
            raise ConversionError(f"Could not reach TikTok: {e}") from e
        if "/music/" in page.url:
            return _convert_tiktok_sound(page.url, page.text, out_dir)
    opts = {
        "format": "bestaudio/best",
        "outtmpl": str(out_dir / "%(id)s.%(ext)s"),
        "noplaylist": True,
        "quiet": not os.environ.get("A2S_DEBUG"),
        "verbose": bool(os.environ.get("A2S_DEBUG")),
        "no_warnings": True,
        "writethumbnail": True,
        "postprocessors": [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"},
            {"key": "FFmpegMetadata", "add_metadata": True},
            {"key": "EmbedThumbnail"},
        ],
    }
    if os.environ.get("A2S_COOKIES_FILE"):
        opts["cookiefile"] = os.environ["A2S_COOKIES_FILE"]
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except yt_dlp.utils.DownloadError as e:
        extra = f" (Cobalt: {cobalt_error})" if cobalt_error else ""
        raise ConversionError(f"Download failed: {e}{extra}") from e

    mp3 = out_dir / f"{info['id']}.mp3"
    if not mp3.exists():
        raise ConversionError("Conversion produced no MP3 (is ffmpeg installed?).")
    artist = info.get("artist") or info.get("uploader") or info.get("channel")
    title = info.get("track") or info.get("title") or info["id"]
    final = out_dir / (safe_filename(f"{artist} - {title}" if artist else title) + ".mp3")
    mp3.rename(final)
    return final
