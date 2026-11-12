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
        "\U0001F300-\U0001F5FF"
        "\U0001F600-\U0001F64F"
        "\U0001F680-\U0001F6FF"
        "\U0001F700-\U0001F77F"
        "\U0001F780-\U0001F7FF"
        "\U0001F800-\U0001F8FF"
        "\U0001F900-\U0001F9FF"
        "\U0001FA00-\U0001FA6F"
        "\U0001FA70-\U0001FAFF"
        "\u2600-\u26FF"
        "\u2700-\u27BF"
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
