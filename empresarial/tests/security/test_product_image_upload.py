"""
Pruebas de Seguridad y Validación de Subida de Imágenes de Productos (F-DC-124).
"""

import io

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def app_and_client():
    application = create_app()
    with TestClient(application) as client:
        yield application, client


def get_auth_token(client: TestClient) -> str:
    res = client.post(
        "/api/auth/login",
        json={"email": "demo.ferreteria@datapyme.co", "password": "DemoFerreteria2026!"},
    )
    assert res.status_code == 200
    return res.json()["access_token"]


def test_valid_image_upload_png(app_and_client):
    _, client = app_and_client
    token = get_auth_token(client)

    # PNG válido mínimo con magic bytes
    valid_png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"

    files = {"file": ("taladro_foto.png", io.BytesIO(valid_png_bytes), "image/png")}
    headers = {"Authorization": f"Bearer {token}"}

    res = client.post("/api/products/upload-image", files=files, headers=headers)
    assert res.status_code == 201
    data = res.json()
    assert "image_url" in data
    assert data["image_url"].startswith("/static/uploads/tenants/")
    assert data["image_url"].endswith(".png")


def test_valid_image_upload_jpeg(app_and_client):
    _, client = app_and_client
    token = get_auth_token(client)

    # JPEG válido mínimo con magic bytes
    valid_jpeg_bytes = (
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00\xff\xd9"
    )

    files = {"file": ("cemento.jpg", io.BytesIO(valid_jpeg_bytes), "image/jpeg")}
    headers = {"Authorization": f"Bearer {token}"}

    res = client.post("/api/products/upload-image", files=files, headers=headers)
    assert res.status_code == 201
    assert res.json()["image_url"].endswith(".jpg")


def test_reject_dangerous_extension(app_and_client):
    _, client = app_and_client
    token = get_auth_token(client)

    # Archivo .exe o ejecutable
    fake_exe = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00"
    files = {"file": ("malware.exe", io.BytesIO(fake_exe), "application/octet-stream")}
    headers = {"Authorization": f"Bearer {token}"}

    res = client.post("/api/products/upload-image", files=files, headers=headers)
    assert res.status_code == 422
    assert "no permitida" in res.json()["detail"].lower()


def test_reject_svg_with_script(app_and_client):
    _, client = app_and_client
    token = get_auth_token(client)

    # SVG no está en la lista de extensiones de subida permitidas para evitar XSS de usuarios
    svg_payload = b'<svg><script>alert("xss")</script></svg>'
    files = {"file": ("icono.svg", io.BytesIO(svg_payload), "image/svg+xml")}
    headers = {"Authorization": f"Bearer {token}"}

    res = client.post("/api/products/upload-image", files=files, headers=headers)
    assert res.status_code == 422


def test_reject_spoofed_magic_bytes(app_and_client):
    _, client = app_and_client
    token = get_auth_token(client)

    # Archivo con extensión .png pero con texto plano adentro
    spoofed = b"ESTO NO ES UN PNG REAL SINO TEXTO FALSO"
    files = {"file": ("fake.png", io.BytesIO(spoofed), "image/png")}
    headers = {"Authorization": f"Bearer {token}"}

    res = client.post("/api/products/upload-image", files=files, headers=headers)
    assert res.status_code == 422
    assert "contenido binario" in res.json()["detail"].lower()


def test_reject_oversized_image(app_and_client):
    _, client = app_and_client
    token = get_auth_token(client)

    # Más de 2 MB
    oversized = b"\xff\xd8\xff" + (b"0" * (2 * 1024 * 1024 + 100))
    files = {"file": ("gigante.jpg", io.BytesIO(oversized), "image/jpeg")}
    headers = {"Authorization": f"Bearer {token}"}

    res = client.post("/api/products/upload-image", files=files, headers=headers)
    assert res.status_code == 413
