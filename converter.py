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


def _convert_tiktok_sound(page_url: str, html: str, out_dir: Path) -> Path:
    """yt-dlp can't extract TikTok *sound* pages, so read the audio URL from the page."""
    m = re.search(
        r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>', html, re.S
    )
    if not m:
        raise ConversionError("TikTok sound page had no embedded data (blocked or changed).")
    music = _find_music(json.loads(m.group(1)))
    if not music:
        raise ConversionError("Could not find the audio URL on the TikTok sound page.")
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
    if "tiktok.com" in url:
        try:
            page = requests.get(url, headers={"User-Agent": BROWSER_UA}, timeout=30)
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
        raise ConversionError(f"Download failed: {e}") from e

    mp3 = out_dir / f"{info['id']}.mp3"
    if not mp3.exists():
        raise ConversionError("Conversion produced no MP3 (is ffmpeg installed?).")
    artist = info.get("artist") or info.get("uploader") or info.get("channel")
    title = info.get("track") or info.get("title") or info["id"]
    final = out_dir / (safe_filename(f"{artist} - {title}" if artist else title) + ".mp3")
    mp3.rename(final)
    return final
