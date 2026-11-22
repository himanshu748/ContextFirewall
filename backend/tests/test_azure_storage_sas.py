"""Synthetic regression cases for Azure Storage SAS URL credentials."""

from app.firewall.secrets import find_secrets, has_secret, redact_text, redacted_kinds


def test_azure_sas_urls_redact_only_signature_value():
    raw = "Ab1+/" * 8 + "xyz="
    encoded = raw.replace("+", "%2B").replace("/", "%2F").replace("=", "%3D")
    for url, signature in (
        (f"https://myacct.blob.core.windows.net/c/a.txt?sv=2024-01-01&sp=r&sig={raw}", raw),
        (f"https://myacct.dfs.core.windows.net/c/a.txt?sig={encoded}&sv=2024-01-01", encoded),
        (f"HTTPS://myacct.file.core.windows.net/share/x?SIG={encoded}", encoded),
        (f"https://myacct.queue.core.windows.net/tasks?sig={raw}", raw),
    ):
        findings = find_secrets(url)
        assert [f.kind for f in findings] == ["azure_sas_signature"], url
        assert url[findings[0].start:findings[0].end] == signature
        masked = redact_text(url)
        assert masked == url.replace(signature, "«REDACTED:azure_sas_signature»")
        assert redacted_kinds(masked) == ["azure_sas_signature"]
        assert not has_secret(masked)


def test_nonazure_and_malformed_sas_urls_are_not_masked_as_sas():
    raw = "Ab1+/" * 8 + "xyz="
    for url in (
        f"https://example.com/c/a.txt?sig={raw}",
        f"https://myacct.blob.core.windows.net.evil.example/c?sig={raw}",
        f"https://myacct.blob.core.windows.net/c?signature={raw}",
        "https://myacct.blob.core.windows.net/c?sig=short",
        "Documentation: sig is a SAS query parameter.",
    ):
        assert [f for f in find_secrets(url) if f.kind == "azure_sas_signature"] == [], url
        assert redact_text(url) == url
