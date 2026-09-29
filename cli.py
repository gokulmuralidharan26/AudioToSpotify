"""Command-line use: python cli.py <url> [output_dir]"""
import sys
from pathlib import Path

from converter import ConversionError, convert

if len(sys.argv) < 2:
    raise SystemExit("usage: python cli.py <youtube-or-tiktok-url> [output_dir]")
out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path.cwd()
out.mkdir(parents=True, exist_ok=True)
try:
    print(convert(sys.argv[1], out))
except ConversionError as e:
    raise SystemExit(str(e))
