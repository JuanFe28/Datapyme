"""
Generador de íconos SVG de alta fidelidad para productos de catálogo y demostración (F-DC-124).
Apple HIG + Shopify Polaris: vectores nítidos, paleta armonizada y rendimiento óptimo.
"""

from pathlib import Path

PRODUCT_SVGS = {
    "cemento.svg": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 80" width="80" height="80">
  <rect width="80" height="80" rx="16" fill="#F1F5F9"/>
  <rect x="22" y="18" width="36" height="44" rx="4" fill="#94A3B8" stroke="#475569" stroke-width="2"/>
  <path d="M26 28h28M26 36h28M26 44h18" stroke="#F8FAFC" stroke-width="2.5" stroke-linecap="round"/>
  <circle cx="50" cy="46" r="4" fill="#0D7A6F"/>
</svg>""",
    "taladro.svg": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 80" width="80" height="80">
  <rect width="80" height="80" rx="16" fill="#F0FDF4"/>
  <path d="M18 34h26v14H18z" fill="#0D7A6F"/>
  <path d="M44 38h16v6H44z" fill="#0A635A"/>
  <path d="M60 40h8v2h-8z" fill="#475569"/>
  <path d="M24 48v16h10V48" fill="#1E293B"/>
  <circle cx="30" cy="41" r="3" fill="#F8FAFC"/>
</svg>""",
    "martillo.svg": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 80" width="80" height="80">
  <rect width="80" height="80" rx="16" fill="#FEF3C7"/>
  <path d="M24 22h32v12H24z" rx="2" fill="#475569"/>
  <path d="M36 34v32h8V34z" rx="2" fill="#D97706"/>
  <path d="M20 25c0-4 4-7 8-7h4v12h-8c-2 0-4-2-4-5z" fill="#334155"/>
</svg>""",
    "pintura.svg": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 80" width="80" height="80">
  <rect width="80" height="80" rx="16" fill="#F0F9FF"/>
  <ellipse cx="40" cy="24" rx="18" ry="6" fill="#38BDF8"/>
  <path d="M22 24v34c0 4 8 7 18 7s18-3 18-7V24" fill="#0284C7"/>
  <path d="M22 36c4 3 14 3 18 0s14-3 18 0" stroke="#BAE6FD" stroke-width="2" fill="none"/>
</svg>""",
    "herramienta.svg": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 80" width="80" height="80">
  <rect width="80" height="80" rx="16" fill="#F8FAFC"/>
  <path d="M26 54L48 32l6 6-22 22z" fill="#64748B"/>
  <circle cx="53" cy="27" r="9" fill="none" stroke="#0D7A6F" stroke-width="4"/>
  <path d="M20 60l6-6-4-4-6 6z" fill="#0F172A"/>
</svg>""",
    "seguridad.svg": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 80" width="80" height="80">
  <rect width="80" height="80" rx="16" fill="#FEF2F2"/>
  <path d="M40 18L22 26v16c0 14 18 22 18 22s18-8 18-22V26L40 18z" fill="#EF4444"/>
  <path d="M33 42l5 5 10-10" stroke="#FFFFFF" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
</svg>""",
    "chaqueta.svg": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 80" width="80" height="80">
  <rect width="80" height="80" rx="16" fill="#EEF2FF"/>
  <path d="M26 22L16 38l8 5 6-11v32h20V32l6 11 8-5-10-16-14 4-14-4z" fill="#4F46E5"/>
  <path d="M40 26v38" stroke="#C7D2FE" stroke-width="2"/>
</svg>""",
    "bolso.svg": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 80" width="80" height="80">
  <rect width="80" height="80" rx="16" fill="#FFFBEB"/>
  <path d="M30 32c0-6 4-12 10-12s10 6 10 12" fill="none" stroke="#B45309" stroke-width="3"/>
  <rect x="22" y="32" width="36" height="30" rx="6" fill="#D97706"/>
  <circle cx="40" cy="44" r="3" fill="#FEF3C7"/>
</svg>""",
    "camisa.svg": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 80" width="80" height="80">
  <rect width="80" height="80" rx="16" fill="#F0FDFA"/>
  <path d="M28 22l-10 8 6 6 6-4v32h20V32l6 4 6-6-10-8-7 4-7-4z" fill="#0D9488"/>
  <circle cx="40" cy="34" r="1.5" fill="#FFFFFF"/>
  <circle cx="40" cy="42" r="1.5" fill="#FFFFFF"/>
  <circle cx="40" cy="50" r="1.5" fill="#FFFFFF"/>
</svg>""",
    "vestido.svg": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 80" width="80" height="80">
  <rect width="80" height="80" rx="16" fill="#FDF2F8"/>
  <path d="M32 20h16v10l8 34H24l8-34V20z" fill="#DB2777"/>
  <path d="M28 36h24" stroke="#FCE7F3" stroke-width="2"/>
</svg>""",
    "calzado.svg": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 80" width="80" height="80">
  <rect width="80" height="80" rx="16" fill="#FAFAF9"/>
  <path d="M18 48c0-8 6-12 14-12h12v12h18v10H18v-10z" rx="4" fill="#78716C"/>
  <rect x="18" y="56" width="44" height="4" rx="2" fill="#1C1917"/>
</svg>""",
    "alimento.svg": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 80" width="80" height="80">
  <rect width="80" height="80" rx="16" fill="#FEFCE8"/>
  <ellipse cx="40" cy="46" rx="22" ry="14" fill="#EAB308"/>
  <ellipse cx="40" cy="38" rx="14" ry="18" fill="#FACC15"/>
  <circle cx="40" cy="38" r="6" fill="#CA8A04"/>
</svg>""",
    "granos.svg": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 80" width="80" height="80">
  <rect width="80" height="80" rx="16" fill="#FFF7ED"/>
  <path d="M32 30c-4 8 2 16 10 16s14-8 10-16-16-8-20 0z" fill="#EA580C"/>
  <path d="M24 46c-3 6 1 12 8 12s10-6 7-12-12-6-15 0z" fill="#C2410C"/>
</svg>""",
    "lacteos.svg": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 80" width="80" height="80">
  <rect width="80" height="80" rx="16" fill="#F8FAFC"/>
  <path d="M30 22h20l6 14v28H24V36l6-14z" fill="#38BDF8"/>
  <rect x="28" y="44" width="24" height="12" rx="2" fill="#FFFFFF"/>
</svg>""",
    "default_product.svg": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 80" width="80" height="80">
  <rect width="80" height="80" rx="16" fill="#F1F5F9"/>
  <path d="M40 22L22 32l18 10 18-10-18-10z" fill="#94A3B8"/>
  <path d="M22 32v18l18 10V42L22 32z" fill="#64748B"/>
  <path d="M58 32v18L40 60V42l18-10z" fill="#475569"/>
</svg>""",
}


def ensure_demo_svg_assets(static_root: Path) -> dict[str, str]:
    """Crea los SVGs en `static/img/products/` y retorna el mapa de nombre a URL."""
    out_dir = static_root / "img" / "products"
    out_dir.mkdir(parents=True, exist_ok=True)
    urls = {}
    for filename, svg_content in PRODUCT_SVGS.items():
        file_path = out_dir / filename
        file_path.write_text(svg_content.strip(), encoding="utf-8")
        urls[filename] = f"/static/img/products/{filename}"
    return urls
