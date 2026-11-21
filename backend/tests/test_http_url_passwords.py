"""HTTP(S) URL userinfo is a bearer-style password disclosure risk."""

from app.firewall.secrets import find_secrets, has_secret, label_for_kind, redact_text


def test_http_basic_auth_urls_are_fully_redacted_without_leaking_password():
    for url in (
        "https://alice:tiny@public.example/path",
        "http://user:p%40ss@public.example/data",
        "https://bob:x@public.example/",
    ):
        raw = "link=" + url
        findings = find_secrets(raw)
        assert any(f.kind == "http_url_password" for f in findings)
        redacted = redact_text(raw)
        assert redacted.startswith("link=«REDACTED:http_url_password»public.example")
        assert ":" + url.split(":", 2)[2].split("@", 1)[0] not in redacted
        assert not has_secret(redacted)
    assert label_for_kind("http_url_password") == "HTTP URL containing embedded credentials"


def test_noncredential_urls_do_not_trigger_http_userinfo_detector():
    for value in (
        "https://public.example/path",
        "https://alice@public.example/path",
        "ftp://alice:secret@public.example/path",
        "prefixhttps://alice:secret@public.example/path",
    ):
        assert all(f.kind != "http_url_password" for f in find_secrets(value)), value
