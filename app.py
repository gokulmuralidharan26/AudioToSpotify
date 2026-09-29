"""Tiny HTTP service: POST a YouTube/TikTok link, get an MP3 back.

Env vars:
  A2S_TOKEN  required shared secret, sent as `Authorization: Bearer <token>`
  PORT       listen port (default 8080)
"""
import hmac
import os
import shutil
from pathlib import Path

from flask import Flask, jsonify, request, send_file

from converter import ConversionError, convert

app = Flask(__name__)
TOKEN = os.environ.get("A2S_TOKEN", "")


def authorized() -> bool:
    supplied = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    return bool(TOKEN) and hmac.compare_digest(supplied, TOKEN)


@app.get("/health")
def health():
    return jsonify(ok=True)


@app.post("/convert")
def convert_route():
    if not authorized():
        return jsonify(error="unauthorized"), 401
    data = request.get_json(silent=True) or {}
    url = data.get("url") or request.form.get("url") or ""
    try:
        mp3 = convert(url)
    except ConversionError as e:
        return jsonify(error=str(e)), 400

    resp = send_file(mp3, mimetype="audio/mpeg", as_attachment=True, download_name=mp3.name)
    resp.call_on_close(lambda: shutil.rmtree(Path(mp3).parent, ignore_errors=True))
    return resp


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("Set A2S_TOKEN before starting the server.")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
