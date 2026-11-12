"""
Servicio seguro de subida y procesamiento de imágenes de productos (F-DC-124).
Aislamiento Multi-Tenant, verificación de magic bytes y mitigación de vulnerabilidades de archivo.
"""

import uuid
from pathlib import Path

from fastapi import HTTPException

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_IMAGE_BYTES = 2 * 1024 * 1024  # 2 MiB


def verify_image_magic_bytes(content: bytes, ext: str) -> bool:
    """Verifica la firma binaria real del archivo para impedir extensiones falsificadas."""
    if len(content) < 12:
        return False
    if ext in (".jpg", ".jpeg"):
        return content.startswith(b"\xff\xd8\xff")
    if ext == ".png":
        return content.startswith(b"\x89PNG\r\n\x1a\n")
    if ext == ".webp":
        return content[:4] == b"RIFF" and content[8:12] == b"WEBP"
    return False


def save_product_image(
    tenant_id: str,
    filename: str,
    content: bytes,
    static_root: Path,
) -> str:
    """
    Valida el archivo contra políticas de seguridad F-DC-124 y lo guarda
    en la ruta aislada del inquilino:
    `static/uploads/tenants/{tenant_id}/products/{uuid}.{ext}`.
    Retorna la URL relativa limpia.
    """
    if not filename:
        raise HTTPException(status_code=422, detail="Nombre de archivo requerido.")

    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Extensión '{ext}' no permitida. Solo se admiten imágenes JPG, JPEG, PNG y WEBP.",
        )

    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=413,
            detail="La imagen supera el límite máximo permitido de 2 MB.",
        )

    if not verify_image_magic_bytes(content, ext):
        raise HTTPException(
            status_code=422,
            detail="El contenido binario del archivo no corresponde a una imagen válida autorizada.",
        )

    safe_tenant_id = "".join(c for c in tenant_id if c.isalnum() or c in "-_")
    if not safe_tenant_id:
        raise HTTPException(status_code=400, detail="Identificador de inquilino inválido.")

    dest_dir = static_root / "uploads" / "tenants" / safe_tenant_id / "products"
    dest_dir.mkdir(parents=True, exist_ok=True)

    unique_filename = f"{uuid.uuid4().hex}{ext}"
    dest_path = dest_dir / unique_filename

    dest_path.write_bytes(content)

    return f"/static/uploads/tenants/{safe_tenant_id}/products/{unique_filename}"
