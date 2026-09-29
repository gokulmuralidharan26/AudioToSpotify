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
