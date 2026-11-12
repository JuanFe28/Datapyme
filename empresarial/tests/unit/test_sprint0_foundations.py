"""Tests de Sprint 0: Salud, cabeceras de seguridad CSP, ausencia de emojis y contraste de tokens."""

import json
import re
from pathlib import Path


def test_health_endpoint(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "datapyme-empresarial"


def test_security_headers_and_csp(client):
    resp = client.get("/health")
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("Referrer-Policy") == "same-origin"
    csp = resp.headers.get("Content-Security-Policy", "")
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp


def test_no_emoji_in_templates_and_static():
    root = Path(__file__).resolve().parents[2]
    emoji_re = re.compile(
        "["
        "\U0001f300-\U0001f5ff"
        "\U0001f600-\U0001f64f"
        "\U0001f680-\U0001f6ff"
        "\U0001f700-\U0001f77f"
        "\U0001f780-\U0001f7ff"
        "\U0001f800-\U0001f8ff"
        "\U0001f900-\U0001f9ff"
        "\U0001fa00-\U0001fa6f"
        "\U0001fa70-\U0001faff"
        "\u2600-\u26ff"
        "\u2700-\u27bf"
        "]+",
        flags=re.UNICODE,
    )
    for folder in ("templates", "static/css", "static/js", "app"):
        target = root / folder
        if not target.exists():
            continue
        for file in target.rglob("*"):
            if file.is_file() and file.suffix in (".html", ".css", ".js", ".py"):
                content = file.read_text(encoding="utf-8")
                match = emoji_re.search(content)
                assert match is None, f"Emoji prohibido detectado en {file}: {match.group(0)}"


def test_design_tokens_and_tabular_nums():
    root = Path(__file__).resolve().parents[2]
    tokens_file = root / "design" / "tokens.json"
    assert tokens_file.exists()
    tokens = json.loads(tokens_file.read_text(encoding="utf-8"))
    assert tokens["typography"]["numeric_variant"] == "tabular-nums"
    assert tokens["colors"]["surface_canvas"] != "#FFFFFF"
    css_file = root / "static" / "css" / "tokens.css"
    assert css_file.exists()
    css_text = css_file.read_text(encoding="utf-8")
    assert "tabular-nums" in css_text
    assert ".bento-grid" in css_text
    assert "rgba(15, 23, 42, 0.06)" in css_text
