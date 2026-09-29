import pytest

import app as app_module
from converter import ConversionError, safe_filename, validate_url


@pytest.mark.parametrize("url", [
    "https://www.youtube.com/watch?v=abc", "https://youtu.be/abc",
    "https://music.youtube.com/watch?v=abc", "https://www.tiktok.com/@u/video/1",
    "https://vm.tiktok.com/ZM123/",
])
def test_valid_urls(url):
    assert validate_url(url) == url


@pytest.mark.parametrize("url", [
    "", "ftp://youtube.com/x", "https://evil.com/?u=youtube.com",
    "https://youtube.com.evil.com/x", "http://169.254.169.254/",
])
def test_invalid_urls(url):
    with pytest.raises(ConversionError):
        validate_url(url)


def test_safe_filename():
    assert safe_filename('a/b:c*"d') == "abcd"
    assert safe_filename("...") == "audio"


def test_auth(monkeypatch):
    monkeypatch.setattr(app_module, "TOKEN", "secret")
    c = app_module.app.test_client()
    assert c.post("/convert", json={"url": "https://youtu.be/x"}).status_code == 401
    r = c.post("/convert", json={"url": "https://evil.com"}, headers={"Authorization": "Bearer secret"})
    assert r.status_code == 400


def test_cobalt_success(monkeypatch, tmp_path):
    import converter

    class Resp:
        status_code = 200
        def __init__(self, payload=None, content=b""):
            self.payload, self.content = payload, content
        def json(self): return self.payload
        def raise_for_status(self): pass
        def iter_content(self, n): yield self.content
        def __enter__(self): return self
        def __exit__(self, *a): pass

    monkeypatch.setenv("COBALT_API_URL", "https://cobalt.example")
    sent = {}
    def fake_post(url, json, headers, timeout):
        sent.update(url=url, json=json, headers=headers)
        return Resp({"status": "tunnel", "url": "https://cobalt.example/t/1", "filename": "a/b: song.mp3"})
    monkeypatch.setattr(converter.requests, "post", fake_post)
    monkeypatch.setattr(converter.requests, "get", lambda *a, **k: Resp(content=b"x" * 20000))
    out = converter.convert("https://youtu.be/abc", tmp_path)
    assert out.name == "b song.mp3" and out.stat().st_size == 20000
    assert sent["json"]["downloadMode"] == "audio" and sent["url"] == "https://cobalt.example/"


def test_cobalt_error_raises(monkeypatch, tmp_path):
    import converter

    class Resp:
        status_code = 401
        def json(self): return {"status": "error", "error": {"code": "error.api.auth.key.missing"}}

    monkeypatch.setenv("COBALT_API_URL", "https://cobalt.example")
    monkeypatch.setattr(converter.requests, "post", lambda *a, **k: Resp())
    with pytest.raises(ConversionError, match="auth.key.missing"):
        converter._convert_cobalt("https://youtu.be/abc", tmp_path)
