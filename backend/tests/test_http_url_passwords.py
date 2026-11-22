"""HTTP(S) URL userinfo is a bearer-style password disclosure risk."""

from app.firewall.secrets import find_secrets, has_secret, label_for_kind, redact_text


def test_http_basic_auth_urls_are_fully_redacted_without_leaking_password():
    # Expected suffixes contain the complete hostname, optional port, and path.
    # In URL authority syntax, the LAST @ separates userinfo from the host.
    for url, expected_suffix in (
        ("https://alice:tiny@public.example/path", "public.example/path"),
        ("http://user:p%40ss@public.example/data", "public.example/data"),
        ("https://bob:x@public.example/", "public.example/"),
        ("https://:tiny@public.example/path", "public.example/path"),
        (
            "https://alice:one:two@public.example:8443/path?q=1#frag",
            "public.example:8443/path?q=1#frag",
        ),
        ("https://alice:one@two@public.example/data", "public.example/data"),
        ("https://al@ice:one@two:three@public.example/path", "public.example/path"),
        ("HTTPS://user:short@public.example/path", "public.example/path"),
    ):
        raw = "link=" + url
        findings = [f for f in find_secrets(raw) if f.kind == "http_url_password"]
        assert len(findings) == 1, url
        assert findings[0].redacted == "***"  # No password suffix in audit previews.
        assert raw[findings[0].start : findings[0].end] == url[: -len(expected_suffix)]

        redacted = redact_text(raw)
        assert redacted == "link=«REDACTED:http_url_password»" + expected_suffix
        assert not has_secret(redacted)

    assert label_for_kind("http_url_password") == "HTTP URL containing embedded credentials"


def test_noncredential_urls_do_not_trigger_http_userinfo_detector():
    for value in (
        "https://public.example/path",
        "https://alice@public.example/path",
        "https://public.example:8443/path",
        "https://public.example/path?q=alice:secret@other.example",
        "ftp://alice:secret@public.example/path",
        "prefixhttps://alice:secret@public.example/path",
    ):
        assert all(f.kind != "http_url_password" for f in find_secrets(value)), value
