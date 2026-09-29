"""Download audio from a YouTube/TikTok link and convert it to a tagged MP3."""
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import urlparse

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


def convert(url: str, out_dir: Path | None = None) -> Path:
    """Download `url` and return the path of the resulting .mp3 file."""
    url = validate_url(url)
    out_dir = Path(out_dir or tempfile.mkdtemp(prefix="a2s_"))
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
