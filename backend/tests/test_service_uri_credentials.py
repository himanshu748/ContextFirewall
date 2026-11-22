"""Regression tests for password-bearing Redis and AMQP service URIs.

All credentials are synthetic; no network service is contacted.
"""
from __future__ import annotations

from app.firewall.secrets import find_secrets, has_secret, redact_text, redacted_kinds


def test_service_uri_credentials_are_blocked_and_fully_masked():
    for prefix in (
        "redis://:",
        "rediss://:",
        "rediss://worker:",
        "amqp://worker:",
        "amqps://worker:",
    ):
        for password in ("x", "yz", "synthetic"):
            url = prefix + password + "@service.example.invalid/resource"
            input_text = "Connect: " + url
            findings = find_secrets(input_text)
            assert [f.kind for f in findings] == ["service_uri_password"], input_text
            masked = redact_text(input_text)
            assert masked == (
                "Connect: «REDACTED:service_uri_password»service.example.invalid/resource"
            )
            assert redacted_kinds(masked) == ["service_uri_password"]
            assert not has_secret(masked)


def test_service_uris_without_passwords_remain_visible():
    for url in (
        "redis://service.example.invalid/0",
        "rediss://service.example.invalid/0",
        "amqp://worker@service.example.invalid/vhost",
        "redis://:@service.example.invalid/0",
    ):
        assert not has_secret(url), url
        assert redact_text(url) == url


def test_existing_redis_userinfo_detection_is_not_duplicated():
    url = "redis://worker:synthetic@service.example.invalid/0"
    assert [f.kind for f in find_secrets(url)] == ["connection_uri_password"]
