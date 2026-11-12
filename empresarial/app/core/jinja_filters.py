"""Filtros y serializadores de Jinja2 para la capa de presentación de Datapyme Empresarial."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from fastapi.templating import Jinja2Templates

from app.core.commercial_service import THREE_PLACES, TWO_PLACES
from app.core.models import Sale


def serialize_sale(sale: Sale) -> dict[str, Any]:
    """Serializa una venta con metadatos completos y detalles de línea para API y vistas."""
    return {
        "id": sale.id,
        "tenant_id": sale.tenant_id,
        "sale_number": sale.sale_number,
        "occurred_at": sale.occurred_at.isoformat() if sale.occurred_at else None,
        "customer_label": sale.customer_label,
        "payment_method": sale.payment_method,
        "subtotal": str(Decimal(str(sale.subtotal)).quantize(TWO_PLACES)),
        "discount_total": str(Decimal(str(sale.discount_total)).quantize(TWO_PLACES)),
        "vat_total": str(Decimal(str(sale.vat_total)).quantize(TWO_PLACES)),
        "total": str(Decimal(str(sale.total)).quantize(TWO_PLACES)),
        "cogs_total": str(Decimal(str(sale.cogs_total)).quantize(TWO_PLACES)),
        "status": sale.status,
        "source": sale.source,
        "items": [
            {
                "id": it.id,
                "product_id": it.product_id,
                "product_name": it.product.name if it.product else "Producto",
                "product_sku": it.product.sku if it.product else "-",
                "product_unit": it.product.unit if it.product else "und",
                "product_image_url": it.product.image_url if it.product else None,
                "quantity": str(Decimal(str(it.quantity)).quantize(THREE_PLACES)),
                "unit_price": str(Decimal(str(it.unit_price)).quantize(TWO_PLACES)),
                "unit_cost_snapshot": str(Decimal(str(it.unit_cost_snapshot)).quantize(TWO_PLACES)),
                "vat_rate": str(Decimal(str(it.vat_rate)).quantize(TWO_PLACES)),
                "discount": str(Decimal(str(it.discount)).quantize(TWO_PLACES)),
                "line_total": str(Decimal(str(it.line_total)).quantize(TWO_PLACES)),
            }
            for it in sale.items
        ],
    }


def format_cop_filter(val: Any) -> str:
    """Formatea valores numéricos a formato de moneda colombiana ($ 1.250.000)."""
    if val is None or val == "" or str(val) == "Undefined":
        return "$ 0"
    try:
        num = float(val)
        rounded = round(num)
        formatted = f"{rounded:,}".replace(",", ".")
        return f"$ {formatted}"
    except (ValueError, TypeError):
        return f"$ {val}"


def format_qty_filter(val: Any, unit: str = "und") -> str:
    """Formatea cantidades de inventario (enteros o decimales limpios)."""
    if val is None or val == "":
        return f"0 {unit}"
    try:
        num = float(val)
        if num.is_integer():
            return f"{int(num)} {unit}"
        formatted = f"{num:.1f}".rstrip("0").rstrip(".")
        return f"{formatted} {unit}"
    except (ValueError, TypeError):
        return f"{val} {unit}"


def format_date_es_filter(val: Any) -> str:
    """Formatea fechas a formato legible en español colombiano."""
    if not val:
        return "-"
    try:
        if isinstance(val, str):
            dt = datetime.fromisoformat(val)
        elif isinstance(val, datetime):
            dt = val
        else:
            return str(val)
        months = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
        month_name = months[dt.month - 1]
        hour_12 = dt.hour % 12 or 12
        am_pm = "a. m." if dt.hour < 12 else "p. m."
        return f"{dt.day} {month_name} {dt.year} · {hour_12}:{dt.minute:02d} {am_pm}"
    except (ValueError, TypeError, AttributeError):
        return str(val)[:16]


def format_payment_label_filter(val: Any) -> str:
    """Traduce métodos de pago técnicos a etiquetas comerciales."""
    m = {
        "cash": "Efectivo",
        "card": "Tarjeta",
        "transfer": "Transferencia",
        "credit": "Crédito",
        "other": "Otro",
    }
    return m.get(str(val or "").lower(), "Efectivo")


def format_pct_filter(val: Any, decimals: int = 1) -> str:
    """Formatea proporciones a porcentaje con coma decimal."""
    if val is None or val == "":
        return "0 %"
    try:
        num = float(val) * 100
        if decimals == 0:
            return f"{round(num)} %"
        return f"{num:.{decimals}f} %".replace(".", ",")
    except (ValueError, TypeError):
        return f"{val} %"


def format_rnd_filter(val: Any, decimals: int = 0) -> str:
    """Redondea números con formato colombiano."""
    if val is None or val == "":
        return "0"
    try:
        num = float(val)
        if decimals == 0:
            return str(round(num))
        return f"{num:.{decimals}f}".replace(".", ",")
    except (ValueError, TypeError):
        return str(val)


def register_jinja_filters(templates: Jinja2Templates) -> None:
    """Registra todos los filtros de presentación en el entorno Jinja2."""
    templates.env.filters["cop"] = format_cop_filter
    templates.env.filters["qty"] = format_qty_filter
    templates.env.filters["date_es"] = format_date_es_filter
    templates.env.filters["payment_label"] = format_payment_label_filter
    templates.env.filters["pct"] = format_pct_filter
    templates.env.filters["rnd"] = format_rnd_filter
