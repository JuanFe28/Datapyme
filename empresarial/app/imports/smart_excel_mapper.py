"""
Servicio de Mapeo Inteligente de Excel Multi-Hoja y Diccionario de Sinónimos Comerciales (F-DC-124).
100% Python puro con openpyxl y csv, cero APIs externas.
"""

import io
import re
import statistics
import unicodedata
import zipfile
from collections import Counter, defaultdict
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import openpyxl
from fastapi import HTTPException

ALLOWED_EXTENSIONS = {".xlsx", ".csv"}
MAX_SCAN_ROWS = 15
MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MiB
MAX_ROWS_LIMIT = 20000

# Diccionario de sinónimos comerciales colombianos normalizados (sin acentos, minúsculas)
SYNONYMS_MAP: dict[str, list[str]] = {
    "vat_rate": ["vat_rate", "iva", "tarifa_iva"],
    "sku": [
        "sku",
        "codigo",
        "ref",
        "referencia",
        "id",
        "item",
        "cod",
        "articulo_id",
        "cod_articulo",
        "referencia_producto",
        "codigo_barra",
    ],
    "name": [
        "nombre",
        "producto",
        "descripcion",
        "articulo",
        "detalle",
        "mercancia",
        "item",
        "nombre_producto",
        "descripcion_producto",
    ],
    "category": [
        "categoria",
        "linea",
        "grupo",
        "familia",
        "tipo",
        "clase",
        "departamento",
        "seccion",
        "rubro",
        "categoria_producto",
    ],
    "cost_price": [
        "costo",
        "precio_costo",
        "costo_unitario",
        "valor_compra",
        "compra",
        "costo_promedio",
        "val_costo",
        "vlr_costo",
        "precio_compra",
    ],
    "sale_price": [
        "precio",
        "precio_venta",
        "venta",
        "pvp",
        "valor",
        "valor_unitario",
        "precio_publico",
        "precio_final",
        "val_venta",
        "vlr_venta",
        "tarifa",
        "precio_unitario",
    ],
    "initial_stock": [
        "stock",
        "cantidad",
        "existencias",
        "unidades",
        "saldo",
        "bodega",
        "inventario",
        "cant",
        "cant_actual",
        "existencia",
        "cant_disponible",
        "disponible",
    ],
    "min_stock": [
        "stock_minimo",
        "min_stock",
        "minimo",
        "alerta_stock",
        "punto_reorden",
        "seguridad",
    ],
    "unit": [
        "unidad",
        "medida",
        "presentacion",
        "unit",
        "und",
        "uom",
    ],
}


def normalize_text(text: str) -> str:
    """Elimina acentos, caracteres especiales y convierte a minúsculas con guiones bajos."""
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(text))
    without_accents = "".join(c for c in nfkd if not unicodedata.combining(c))
    cleaned = re.sub(r"[^\w\s]", "", without_accents).strip().lower()
    return re.sub(r"[\s\-]+", "_", cleaned)


def clean_currency_or_number_string(val: Any) -> str:
    """
    Limpia cadenas numéricas y monetarias colombianas ($ 125.000,00 -> 125000.00).
    Maneja comas y puntos según el estándar contable.
    """
    if val is None:
        return "0"
    s = str(val).strip()
    if not s or s.lower() in ("none", "null", "nan", "-"):
        return "0"
    # Eliminar signo peso, espacios y letras
    cleaned = re.sub(r"[^\d.,\-]", "", s)
    if not cleaned:
        return "0"

    # Si contiene punto y coma: detectar si punto es miles y coma es decimal
    if "." in cleaned and "," in cleaned:
        # En Colombia $ 1.250.000,50 -> punto miles, coma decimal
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            # 1,250,000.50 -> coma miles, punto decimal
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        # Solo coma: si tiene 2 dígitos al final, es decimal; si tiene 3, podría ser miles
        parts = cleaned.split(",")
        if len(parts) == 2 and len(parts[1]) in (1, 2):
            cleaned = cleaned.replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "." in cleaned:
        # Solo puntos: si tiene más de un punto, son separadores de miles ($ 1.250.000)
        if cleaned.count(".") > 1:
            cleaned = cleaned.replace(".", "")
        else:
            parts = cleaned.split(".")
            # Si tiene 3 dígitos después del único punto ($ 25.000), en Colombia es miles
            if len(parts) == 2 and len(parts[1]) == 3 and int(parts[0]) >= 1:
                cleaned = cleaned.replace(".", "")
    return cleaned or "0"


IGNORED_SHEET_KEYWORDS = (
    "dashboard",
    "resumen",
    "estado_financiero",
    "inversion",
    "inversiones",
    "gasto",
    "gastos",
    "egreso",
    "egresos",
    "nomina",
    "balance",
)

IGNORED_TITLE_KEYWORDS = (
    "estado_financiero",
    "inversion_inicial",
    "gastos_sacados",
    "resumen_gastos",
    "gastos_del_flujo",
)

IGNORED_ROW_TERMS = {
    "total",
    "subtotal",
    "resumen",
    "resumen_flujo",
    "utilidad",
    "utilidad_neta",
    "inversion",
    "total_inversion",
    "total_ingresos",
    "total_gastos",
    "pago_vale",
    "pago_juan",
    "pasaje",
    "aporte",
    "efectivo",
    "transferencia",
}

CANONICAL_PRODUCT_ALIASES: dict[str, str] = {
    "clasico": "Clásico",
    "supreme": "Supreme",
    "supremo": "Supreme",
    "bite": "Bite",
    "bites": "Bite",
    "mini": "Mini",
    "minis": "Mini",
    "adicional": "Adicional",
    "adicionales": "Adicional",
}


def _is_ignored_sheet(sheet_name: str, matrix: list[list[Any]]) -> bool:
    norm_s = normalize_text(sheet_name)
    if any(kw in norm_s for kw in IGNORED_SHEET_KEYWORDS):
        return True
    top_cells = [
        normalize_text(str(c)) for row in matrix[:4] for c in row if c is not None and str(c).strip()
    ]
    joined = " ".join(top_cells)
    return any(kw in joined for kw in IGNORED_TITLE_KEYWORDS)


def _extract_contiguous_header_block(row: list[Any]) -> tuple[int, list[str]]:
    """Extrae el bloque contiguo principal de encabezados ignorando márgenes y cuadros laterales."""
    start = 0
    while start < len(row) and (row[start] is None or not str(row[start]).strip()):
        start += 1
    if start >= len(row):
        return 0, []
    headers: list[str] = []
    idx = start
    while idx < len(row):
        val = str(row[idx] or "").strip()
        if not val:
            break
        headers.append(val)
        idx += 1
    return start, headers


def canonicalize_product_name(raw_name: str, seen_canonical: dict[str, str] | None = None) -> str:
    """Normaliza variantes ortográficas, tildes y mayúsculas de un producto."""
    cleaned = re.sub(r"\s+", " ", _clean_unified_text(raw_name, 180)).strip()
    if not cleaned:
        return ""
    key = normalize_text(cleaned)
    if key in CANONICAL_PRODUCT_ALIASES:
        return CANONICAL_PRODUCT_ALIASES[key]
    if seen_canonical is not None:
        if key in seen_canonical:
            prev = seen_canonical[key]
            if any(ord(ch) > 127 for ch in cleaned) and not any(ord(ch) > 127 for ch in prev):
                seen_canonical[key] = cleaned
            return seen_canonical[key]
        pretty = cleaned.title() if cleaned.islower() or cleaned.isupper() else cleaned
        seen_canonical[key] = pretty
        return pretty
    return cleaned.title() if cleaned.islower() or cleaned.isupper() else cleaned


def _split_raw_product_combo_items(
    raw_text: str,
    seen_canonical: dict[str, str] | None = None,
) -> list[tuple[str, Decimal]]:
    """Extrae lista de (producto_canonico, cantidad) desde celdas simples o con combos."""
    s = re.sub(r"\s+", " ", _clean_unified_text(raw_text, 180)).strip()
    if not s:
        return []
    s = re.sub(r"\((\d+(?:[.,]\d+)?)\)", r" x\1", s)
    s = re.sub(r"(?i)([a-záéíóúñ]{2,})\s*[x*]\s*(\d+(?:[.,]\d+)?)(?![a-z])", r"\1 x\2", s)
    s = re.sub(r"(?i)(\bx\s*\d+(?:[.,]\d+)?)\s+(?=[a-záéíóúñ])", r"\1 | ", s)
    parts = re.split(r"\s*(?:\||\/|\+|&|\s+y\s+|\s+e\s+)\s*", s, flags=re.IGNORECASE)

    parsed: list[tuple[str, Decimal]] = []
    for part in parts:
        chunk = part.strip()
        if not chunk:
            continue
        m = re.search(
            r"(?i)(?:^|\s)[x*]\s*(\d+(?:[.,]\d+)?)(?!\s*(?:cm|mm|m|ml|g|kg|oz|lb|w)\b)\s*$",
            chunk,
        )
        if not m:
            m = re.search(
                r"(?i)\bx\s*(\d+(?:[.,]\d+)?)(?!\s*(?:cm|mm|m|ml|g|kg|oz|lb|w)\b)\b",
                chunk,
            )
        qty = Decimal("1.000")
        name_part = chunk
        if m:
            try:
                q_val = Decimal(m.group(1).replace(",", ".")).quantize(Decimal("0.001"))
                if q_val > 0:
                    qty = q_val
            except (InvalidOperation, ValueError):
                qty = Decimal("1.000")
            name_part = (chunk[: m.start()] + " " + chunk[m.end() :]).strip()
        cname = canonicalize_product_name(name_part, seen_canonical)
        if cname:
            parsed.append((cname, qty))
    return parsed


def parse_product_cell_and_combos(
    raw_text: str,
    line_value: Decimal,
    known_unit_prices: dict[str, Decimal] | None = None,
    seen_canonical: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """
    Descompone una celda de producto (con multiplicadores xN y/o combos combinados)
    en ítems normalizados repartiendo proporcionalmente `line_value` al peso exacto.
    """
    items = _split_raw_product_combo_items(raw_text, seen_canonical)
    if not items:
        return []

    total_val = Decimal(line_value).quantize(Decimal("0.01"))
    prices_map = known_unit_prices or {}

    if len(items) == 1:
        name, qty = items[0]
        unit_p = (
            (total_val / qty).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if qty > 0 else total_val
        )
        return [
            {
                "product_name": name,
                "quantity": qty.quantize(Decimal("0.001")),
                "unit_price": unit_p,
                "line_total": total_val,
            }
        ]

    expected_weights: list[Decimal] = []
    for name, qty in items:
        base_p = prices_map.get(name) or Decimal("0.00")
        w = (qty * base_p) if base_p > 0 else qty
        expected_weights.append(w)

    sum_weights = sum(expected_weights, Decimal("0.00"))
    if sum_weights <= 0:
        expected_weights = [qty for _, qty in items]
        sum_weights = sum(expected_weights, Decimal("0.00"))

    result: list[dict[str, Any]] = []
    allocated = Decimal("0.00")
    for idx, (name, qty) in enumerate(items):
        if idx == len(items) - 1:
            part_total = (total_val - allocated).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        else:
            ratio = expected_weights[idx] / sum_weights
            part_total = (total_val * ratio).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            allocated += part_total
        unit_p = (
            (part_total / qty).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if qty > 0
            else part_total
        )
        result.append(
            {
                "product_name": name,
                "quantity": qty.quantize(Decimal("0.001")),
                "unit_price": unit_p,
                "line_total": part_total,
            }
        )
    return result


def inspect_workbook(
    filename: str,
    content: bytes,
    target_sheet: str | None = None,
) -> dict[str, Any]:
    """
    Inspecciona un archivo .xlsx o .csv:
    1. Lee todas las hojas.
    2. Detecta automáticamente la fila de encabezado en las primeras 15 filas.
    3. Auto-mapea las columnas usando sinónimos comerciales.
    4. Extrae previsualización de las primeras 3 filas de datos.
    """
    if not filename:
        raise HTTPException(status_code=422, detail="Nombre de archivo requerido.")
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Extensión '{ext}' no soportada. Solo se admiten archivos .xlsx y .csv.",
        )
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="El archivo supera el límite de 5 MB.")

    sheets: list[str] = []
    raw_matrix: list[list[Any]] = []

    if ext == ".csv":
        sheets = ["Hoja Principal"]
        from app.imports.batch_importer import read_csv_matrix

        raw_matrix = read_csv_matrix(content)[: MAX_SCAN_ROWS + 10]
        selected_sheet = sheets[0]
    else:
        if not content.startswith(b"PK\x03\x04"):
            raise HTTPException(
                status_code=422, detail="El archivo no es un Excel válido (firma ZIP inválida)."
            )
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                total_uncompressed = sum(info.file_size for info in zf.infolist())
                if total_uncompressed > 25 * 1024 * 1024:
                    raise HTTPException(
                        status_code=422, detail="Archivo Excel excede límite descomprimido."
                    )
        except zipfile.BadZipFile as exc:
            raise HTTPException(status_code=422, detail="Archivo XLSX corrupto.") from exc

        wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        sheets = list(wb.sheetnames)
        if not sheets:
            raise HTTPException(status_code=422, detail="El libro de Excel no contiene hojas.")

        def _read_ws_head(ws_obj) -> list[list[Any]]:
            mat: list[list[Any]] = []
            for row_idx, row in enumerate(ws_obj.iter_rows(values_only=True), start=1):
                mat.append(list(row))
                if row_idx >= MAX_SCAN_ROWS + 10:
                    break
            return mat

        if target_sheet and target_sheet in sheets:
            selected_sheet = target_sheet
            raw_matrix = _read_ws_head(wb[selected_sheet])
        else:
            selected_sheet = sheets[0]
            for cand in sheets:
                cand_mat = _read_ws_head(wb[cand])
                if not _is_ignored_sheet(cand, cand_mat):
                    selected_sheet = cand
                    raw_matrix = cand_mat
                    break
            if not raw_matrix:
                raw_matrix = _read_ws_head(wb[selected_sheet])
        wb.close()

    # Detección inteligente de fila de encabezados en las primeras 15 filas
    best_row_idx = 0
    best_score = -1.0
    col_offset = 0
    best_headers: list[str] = []

    all_synonyms = (
        set(SYNONYMS_MAP)
        | {syn for syn_list in SYNONYMS_MAP.values() for syn in syn_list}
        | set(UNIFIED_SALE_SYNONYMS)
        | {syn for syn_list in UNIFIED_SALE_SYNONYMS.values() for syn in syn_list}
    )

    for row_idx, row in enumerate(raw_matrix[:MAX_SCAN_ROWS]):
        offset, block_headers = _extract_contiguous_header_block(row)
        if len(block_headers) < 2:
            continue
        score = 0.0
        for cell in block_headers:
            norm = normalize_text(cell)
            if norm in all_synonyms:
                score += 3.0
            elif any(syn in norm for syn in all_synonyms):
                score += 1.0
            elif re.search(r"[a-zA-Z]", norm):
                score += 0.2
        if score > best_score:
            best_score = score
            best_row_idx = row_idx
            col_offset = offset
            best_headers = block_headers

    if not best_headers:
        for row_idx, row in enumerate(raw_matrix):
            offset, block_headers = _extract_contiguous_header_block(row)
            if block_headers:
                best_row_idx = row_idx
                col_offset = offset
                best_headers = block_headers
                break

    columns = [h if h else f"Columna_{i + 1}" for i, h in enumerate(best_headers)]

    sales_mapping: dict[str, str | None] = {
        "occurred_at": None,
        "product": None,
        "payment_method": None,
        "total": None,
    }
    sale_hits = 0
    for col in columns:
        norm = normalize_text(col)
        if not sales_mapping["occurred_at"] and _match_synonyms(
            norm, UNIFIED_SALE_SYNONYMS["occurred_at"]
        ):
            sales_mapping["occurred_at"] = col
            sale_hits += 1
        elif not sales_mapping["payment_method"] and _match_synonyms(
            norm, UNIFIED_SALE_SYNONYMS["payment_method"]
        ):
            sales_mapping["payment_method"] = col
            sale_hits += 1
        elif not sales_mapping["total"] and (
            _match_synonyms(norm, UNIFIED_SALE_SYNONYMS["line_total"])
            or norm in ("valor", "total", "monto", "importe")
        ):
            sales_mapping["total"] = col
            sale_hits += 1
        elif not sales_mapping["product"] and _match_synonyms(norm, ["nombre", *SYNONYMS_MAP["name"]]):
            sales_mapping["product"] = col

    is_sales_sheet = sale_hits >= 2 or any(
        kw in normalize_text(selected_sheet) for kw in ("venta", "flujo", "factur", "sale", "pos")
    )

    # Auto-Mapeo usando sinónimos comerciales
    suggested_mapping: dict[str, str | None] = {
        "vat_rate": None,
        "sku": None,
        "name": None,
        "category": None,
        "cost_price": None,
        "sale_price": None,
        "initial_stock": None,
        "min_stock": None,
        "unit": None,
    }

    assigned_cols: set[str] = set()
    blocked_for_catalog = {
        c
        for c in (sales_mapping.get("occurred_at"), sales_mapping.get("payment_method"))
        if c is not None
    }

    for field, synonyms in SYNONYMS_MAP.items():
        synonyms = [field, *synonyms]
        for col in columns:
            if col in assigned_cols or col in blocked_for_catalog:
                continue
            norm = normalize_text(col)
            if (
                is_sales_sheet
                and field
                in (
                    "sku",
                    "vat_rate",
                    "cost_price",
                    "initial_stock",
                    "min_stock",
                )
                and norm in ("valor", "total", "fecha", "metodo_pago")
            ):
                continue
            # Coincidencia exacta o contenida
            if norm in synonyms or any(
                norm == syn or norm.startswith(syn + "_") or norm.endswith("_" + syn) for syn in synonyms
            ):
                suggested_mapping[field] = col
                assigned_cols.add(col)
                break

    # Extraer previsualización de 3 filas posteriores al encabezado
    sample_rows: list[dict[str, Any]] = []
    data_rows = raw_matrix[best_row_idx + 1 : best_row_idx + 6]

    for d_row in data_rows:
        slice_row = d_row[col_offset : col_offset + len(columns)]
        if not any(c is not None and str(c).strip() for c in slice_row):
            continue
        row_dict: dict[str, Any] = {}
        for c_idx, col_name in enumerate(columns):
            val = slice_row[c_idx] if c_idx < len(slice_row) else ""
            if isinstance(val, datetime):
                row_dict[col_name] = val.strftime("%Y-%m-%d")
            else:
                row_dict[col_name] = "" if val is None else str(val).strip()
        sample_rows.append(row_dict)
        if len(sample_rows) >= 3:
            break

    return {
        "filename": filename,
        "sheets": sheets,
        "selected_sheet": selected_sheet,
        "sheet_kind": "sales" if is_sales_sheet else "products",
        "header_row_index": best_row_idx + 1,  # 1-indexed para humanos
        "col_offset": col_offset,
        "columns": columns,
        "suggested_mapping": suggested_mapping,
        "sales_mapping": sales_mapping,
        "sample_rows": sample_rows,
    }


def parse_mapped_workbook_products(
    filename: str,
    content: bytes,
    mapping: dict[str, str],
    sheet_name: str | None = None,
    header_row_index: int = 1,
) -> list[dict[str, Any]]:
    """
    Lee el archivo completo aplicando el mapeo de columnas del usuario o inferido.
    Auto-genera SKU consecutivo si la columna de SKU no fue mapeada o viene vacía.
    Formatea y valida precios y existencias en COP.
    """
    ext = Path(filename).suffix.lower()
    inspect_workbook(filename, content, target_sheet=sheet_name)
    raw_rows: list[list[Any]] = []

    if ext == ".csv":
        from app.imports.batch_importer import read_csv_matrix

        raw_rows = read_csv_matrix(content)
    else:
        wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        sheets = list(wb.sheetnames)
        target = sheet_name if (sheet_name and sheet_name in sheets) else sheets[0]
        ws = wb[target]
        for row in ws.iter_rows(values_only=True):
            raw_rows.append(list(row))
        wb.close()

    if len(raw_rows) < header_row_index:
        return []

    header_cells = raw_rows[header_row_index - 1]
    col_to_idx: dict[str, int] = {}
    for idx, c in enumerate(header_cells):
        col_str = str(c or "").strip()
        if col_str and col_str not in col_to_idx:
            col_to_idx[col_str] = idx

    # Invertir mapeo: field -> col_idx
    field_to_idx: dict[str, int] = {}
    for field, col_name in mapping.items():
        if col_name and col_name in col_to_idx:
            field_to_idx[field] = col_to_idx[col_name]

    parsed_products: list[dict[str, Any]] = []
    auto_sku_counter = 1

    def get_val(row: list[Any], field: str) -> str:
        if field in field_to_idx:
            idx = field_to_idx[field]
            if idx < len(row) and row[idx] is not None:
                return str(row[idx]).strip()
        return ""

    for row_num, row_data in enumerate(raw_rows[header_row_index:], start=header_row_index + 1):
        if not any(c is not None and str(c).strip() for c in row_data):
            continue

        raw_name = get_val(row_data, "name")
        if not raw_name:
            continue

        raw_sku = get_val(row_data, "sku")
        if not raw_sku:
            raw_sku = f"AUTO-{auto_sku_counter:04d}"
            auto_sku_counter += 1

        category = get_val(row_data, "category") or "General"
        unit = get_val(row_data, "unit") or "und"

        def read_number(raw: str, field: str, precision: str, row_number: int) -> Decimal:
            try:
                cleaned_input = raw.replace("COP", "").replace("$", "").replace(" ", "")
                if cleaned_input and not re.fullmatch(r"-?\d+(?:[.,]\d+)*", cleaned_input):
                    raise ValueError("Texto mezclado con números")
                if raw and raw != "-" and not re.search(r"\d", raw):
                    raise ValueError("Valor no numérico")
                normalized = clean_currency_or_number_string(raw)
                if (
                    precision == "0.001"
                    and "," in cleaned_input
                    and "." not in cleaned_input
                    and cleaned_input.count(",") == 1
                ):
                    normalized = cleaned_input.replace(",", ".")
                number = Decimal(normalized).quantize(Decimal(precision))
                if not number.is_finite() or number < 0:
                    raise ValueError("Valor negativo o no finito")
                return number
            except (InvalidOperation, ValueError, TypeError) as exc:
                raise HTTPException(
                    status_code=422,
                    detail=f"Fila {row_number}: {field} debe ser un número válido no negativo.",
                ) from exc

        cost_dec = read_number(get_val(row_data, "cost_price"), "cost_price", "0.01", row_num)
        sale_dec = read_number(get_val(row_data, "sale_price"), "sale_price", "0.01", row_num)
        stock_dec = read_number(get_val(row_data, "initial_stock"), "initial_stock", "0.001", row_num)
        min_stock_dec = read_number(get_val(row_data, "min_stock"), "min_stock", "0.001", row_num)
        vat_dec = read_number(get_val(row_data, "vat_rate") or "19", "vat_rate", "0.01", row_num)
        if vat_dec > 100:
            raise HTTPException(status_code=422, detail=f"Fila {row_num}: tarifa IVA fuera de rango.")

        parsed_products.append(
            {
                "sku": raw_sku.upper()[:64],
                "name": raw_name[:180],
                "category": category[:90],
                "unit": unit[:20],
                "cost_price": cost_dec,
                "sale_price": sale_dec,
                "vat_rate": vat_dec,
                "initial_stock": stock_dec,
                "min_stock": min_stock_dec,
                "row_number": row_num,
            }
        )

        if len(parsed_products) > MAX_ROWS_LIMIT:
            raise HTTPException(status_code=422, detail="El archivo supera el límite de 20.000 filas.")

    return parsed_products


UNIFIED_SALE_SYNONYMS: dict[str, list[str]] = {
    "sale_number": [
        "sale_number",
        "factura",
        "recibo",
        "comprobante",
        "nro_venta",
        "numero_venta",
        "ticket",
        "pedido",
        "orden",
        "referencia_venta",
    ],
    "occurred_at": [
        "occurred_at",
        "fecha",
        "fecha_venta",
        "fec_venta",
        "fecha_hora",
        "date",
        "dia",
    ],
    "quantity_sold": [
        "cantidad_vendida",
        "unidades_vendidas",
        "qty_sold",
        "vendido",
        "vendidas",
        "cant_vendida",
        "quantity",
        "cantidad",
        "cant",
    ],
    "unit_price": [
        "unit_price",
        "precio_unitario",
        "precio_venta",
        "precio",
        "valor_unitario",
        "pvp",
        "valor",
    ],
    "line_total": [
        "total",
        "total_venta",
        "subtotal",
        "monto",
        "importe",
        "valor_total",
        "neto",
    ],
    "customer_label": [
        "customer_label",
        "cliente",
        "customer",
        "comprador",
        "razon_social",
    ],
    "payment_method": [
        "payment_method",
        "medio_pago",
        "metodo_pago",
        "forma_pago",
        "pago",
    ],
    "discount": [
        "discount",
        "descuento",
        "dcto",
    ],
}

_PAYMENT_ALIASES: dict[str, str] = {
    "efectivo": "cash",
    "cash": "cash",
    "contado": "cash",
    "tarjeta": "card",
    "card": "card",
    "debito": "card",
    "datafono": "card",
    "transferencia": "transfer",
    "transfer": "transfer",
    "nequi": "transfer",
    "daviplata": "transfer",
    "pse": "transfer",
    "bancolombia": "transfer",
    "credito": "credit",
    "credit": "credit",
    "fiado": "credit",
}


def _match_synonyms(norm_header: str, candidates: list[str]) -> bool:
    return norm_header in candidates or any(
        norm_header == syn or norm_header.startswith(syn + "_") or norm_header.endswith("_" + syn)
        for syn in candidates
    )


def _normalize_unified_decimal(raw_val: Any, precision: str = "0.01", default: str = "0") -> Decimal:
    if raw_val is None:
        return Decimal(default).quantize(Decimal(precision))
    s = str(raw_val).strip()
    if not s or s.lower() in ("none", "null", "nan", "-"):
        return Decimal(default).quantize(Decimal(precision))
    cleaned_input = s.replace("COP", "").replace("$", "").replace(" ", "")
    if not re.fullmatch(r"-?\d+(?:[.,]\d+)*", cleaned_input):
        return Decimal(default).quantize(Decimal(precision))
    normalized = clean_currency_or_number_string(s)
    if (
        precision == "0.001"
        and "," in cleaned_input
        and "." not in cleaned_input
        and cleaned_input.count(",") == 1
    ):
        normalized = cleaned_input.replace(",", ".")
    try:
        dec = Decimal(normalized).quantize(Decimal(precision))
        return dec if dec.is_finite() and dec >= 0 else Decimal(default).quantize(Decimal(precision))
    except (InvalidOperation, ValueError):
        return Decimal(default).quantize(Decimal(precision))


def _normalize_unified_date(raw_val: Any) -> str:
    if raw_val is None:
        return ""
    if isinstance(raw_val, datetime):
        return raw_val.strftime("%Y-%m-%d")
    if isinstance(raw_val, date):
        return raw_val.isoformat()
    text = str(raw_val).strip()
    if not text:
        return ""
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text[:19], fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text).date().isoformat()
    except ValueError:
        return ""


def _normalize_payment(raw_val: Any) -> str:
    norm = normalize_text(str(raw_val or ""))
    return _PAYMENT_ALIASES.get(norm, "cash")


def _clean_unified_text(raw_val: Any, max_len: int = 180) -> str:
    s = str(raw_val or "").strip()
    while s and s[0] in ("=", "+", "-", "@", "\t", "\r"):
        s = s[1:].strip()
    return s[:max_len].strip()


def _detect_sheet_header_and_maps(
    raw_rows: list[list[Any]],
) -> tuple[int, list[str], dict[str, int], dict[str, int]]:
    prod_syns = {k: [k, *v] for k, v in SYNONYMS_MAP.items()}
    sale_syns = {k: [k, *v] for k, v in UNIFIED_SALE_SYNONYMS.items()}
    all_syns = {s for vals in (*prod_syns.values(), *sale_syns.values()) for s in vals}

    best_idx = 0
    best_score = -1.0
    col_offset = 0
    best_headers: list[str] = []
    for idx, row in enumerate(raw_rows[:MAX_SCAN_ROWS]):
        offset, block_headers = _extract_contiguous_header_block(row)
        if len(block_headers) < 2:
            continue
        score = 0.0
        for cell_txt in block_headers:
            norm = normalize_text(cell_txt)
            if norm in all_syns:
                score += 3.0
            elif any(s in norm for s in all_syns):
                score += 1.0
            elif re.search(r"[a-zA-Z]", norm):
                score += 0.2
        if score > best_score:
            best_score = score
            best_idx = idx
            col_offset = offset
            best_headers = block_headers

    columns = [h if h else f"Columna_{i + 1}" for i, h in enumerate(best_headers)]

    prod_idx: dict[str, int] = {}
    sale_idx: dict[str, int] = {}
    for rel_i, col_name in enumerate(columns):
        abs_i = col_offset + rel_i
        norm = normalize_text(col_name)
        for field, syns in prod_syns.items():
            if field not in prod_idx and _match_synonyms(norm, syns):
                prod_idx[field] = abs_i
        for field, syns in sale_syns.items():
            if field not in sale_idx and _match_synonyms(norm, syns):
                sale_idx[field] = abs_i

    return best_idx, columns, prod_idx, sale_idx


def _is_ignored_summary_row(raw_text: str) -> bool:
    norm = normalize_text(raw_text)
    if not norm:
        return True
    if norm in IGNORED_ROW_TERMS:
        return True
    return any(
        norm.startswith(prefix)
        for prefix in ("total_", "resumen_", "utilidad_", "pago_vale", "pago_juan", "gastos_")
    )


def analyze_unified_workbook(filename: str, content: bytes) -> dict[str, Any]:
    """
    Analizador unificado 100% determinista para cualquier Excel (.xlsx) o CSV.
    - Ignora hojas gerenciales/inversión/gastos y filas de totales/resúmenes.
    - Normaliza tildes/variantes y separa cantidades (xN) y combos en celdas de producto.
    - Calcula precios unitarios sugeridos y reparte proporcionalmente los combos al peso exacto.
    """
    if not filename:
        raise HTTPException(status_code=422, detail="Nombre de archivo requerido.")
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Extensión '{ext}' no soportada. Solo se admiten archivos .xlsx y .csv.",
        )
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="El archivo supera el límite de 5 MB.")

    sheets_matrices: list[tuple[str, list[list[Any]]]] = []
    if ext == ".csv":
        from app.imports.batch_importer import read_csv_matrix

        sheets_matrices.append(("Hoja Principal", read_csv_matrix(content)))
    else:
        if not content.startswith(b"PK\x03\x04"):
            raise HTTPException(
                status_code=422, detail="El archivo no es un Excel válido (firma ZIP inválida)."
            )
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                if sum(info.file_size for info in zf.infolist()) > 25 * 1024 * 1024:
                    raise HTTPException(
                        status_code=422, detail="Archivo XLSX excede límite descomprimido."
                    )
        except zipfile.BadZipFile as exc:
            raise HTTPException(status_code=422, detail="Archivo XLSX corrupto.") from exc

        wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        if not wb.sheetnames:
            wb.close()
            raise HTTPException(status_code=422, detail="El libro de Excel no contiene hojas.")
        for s_name in wb.sheetnames:
            ws = wb[s_name]
            matrix: list[list[Any]] = []
            for row in ws.iter_rows(values_only=True):
                matrix.append(list(row))
                if len(matrix) > MAX_ROWS_LIMIT + MAX_SCAN_ROWS:
                    break
            sheets_matrices.append((s_name, matrix))
        wb.close()

    products_by_key: dict[str, dict[str, Any]] = {}
    name_to_key: dict[str, str] = {}
    seen_canonical: dict[str, str] = {}
    unit_price_samples: dict[str, list[Decimal]] = defaultdict(list)
    units_sold_by_name: dict[str, Decimal] = defaultdict(Decimal)
    pending_sale_rows: list[dict[str, Any]] = []
    auto_sku_seq = 1
    sale_seq = 1

    def cell(row: list[Any], idx_map: dict[str, int], key: str) -> Any:
        i = idx_map.get(key)
        if i is None or i >= len(row):
            return None
        return row[i]

    def register_product(
        *,
        sku_raw: str,
        name_raw: str,
        category: str,
        unit: str,
        cost_price: Decimal,
        sale_price: Decimal,
        vat_rate: Decimal,
        initial_stock: Decimal,
        min_stock: Decimal,
        sheet_name: str,
    ) -> dict[str, Any]:
        nonlocal auto_sku_seq
        clean_name = canonicalize_product_name(name_raw, seen_canonical)
        clean_sku = _clean_unified_text(sku_raw, 64).upper()
        name_key = normalize_text(clean_name)

        if clean_sku and clean_sku in products_by_key:
            prod = products_by_key[clean_sku]
            if prod["cost_price"] == Decimal("0.00") and cost_price > 0:
                prod["cost_price"] = cost_price
            if prod["sale_price"] == Decimal("0.00") and sale_price > 0:
                prod["sale_price"] = sale_price
            if prod["initial_stock"] == Decimal("0.000") and initial_stock > 0:
                prod["initial_stock"] = initial_stock
            return prod
        if not clean_sku and name_key and name_key in name_to_key:
            prod = products_by_key[name_to_key[name_key]]
            if prod["sale_price"] == Decimal("0.00") and sale_price > 0:
                prod["sale_price"] = sale_price
            return prod

        if not clean_sku:
            while f"AUTO-{auto_sku_seq:04d}" in products_by_key:
                auto_sku_seq += 1
            clean_sku = f"AUTO-{auto_sku_seq:04d}"
            auto_sku_seq += 1

        prod_entry = {
            "sku": clean_sku,
            "name": clean_name or clean_sku,
            "category": _clean_unified_text(category, 90) or "General",
            "unit": _clean_unified_text(unit, 20) or "und",
            "cost_price": cost_price,
            "sale_price": sale_price,
            "vat_rate": vat_rate if vat_rate <= Decimal("100.00") else Decimal("0.00"),
            "initial_stock": initial_stock,
            "min_stock": min_stock,
            "sheet_name": sheet_name,
        }
        products_by_key[clean_sku] = prod_entry
        if name_key:
            name_to_key[name_key] = clean_sku
        return prod_entry

    for sheet_name, matrix in sheets_matrices:
        if not matrix or _is_ignored_sheet(sheet_name, matrix):
            continue
        hdr_idx, _cols, p_map, s_map = _detect_sheet_header_and_maps(matrix)
        if not p_map and not s_map:
            continue

        norm_sheet = normalize_text(sheet_name)
        is_sale_sheet_name = bool(
            re.search(
                r"(?:^|_)(ventas?|flujo|factur\w*|sales?|pos|pedidos?|historial|comprobantes?)(?:$|_)",
                norm_sheet,
            )
        )

        # Si la hoja es un libro de ventas sin columna de cantidad ni de total explícito
        # (ej. FECHA | PRODUCTO | MÉTODO PAGO | VALOR), 'VALOR' representa el total de la venta.
        if (
            "line_total" not in s_map
            and "quantity_sold" not in s_map
            and "unit_price" in s_map
            and (
                is_sale_sheet_name
                or any(k in s_map for k in ("occurred_at", "payment_method", "sale_number"))
            )
        ):
            up_idx = s_map["unit_price"]
            up_hdr = (
                normalize_text(str(matrix[hdr_idx][up_idx] or ""))
                if up_idx < len(matrix[hdr_idx])
                else ""
            )
            if "unitario" not in up_hdr and "unit" not in up_hdr:
                s_map["line_total"] = s_map.pop("unit_price")
                if p_map.get("sale_price") == up_idx:
                    p_map.pop("sale_price", None)

        explicit_sale_col = any(
            k in s_map
            for k in ("occurred_at", "sale_number", "customer_label", "payment_method", "line_total")
        )
        qty_col_idx = s_map.get("quantity_sold")
        qty_header_norm = ""
        if qty_col_idx is not None and qty_col_idx < len(matrix[hdr_idx]):
            qty_header_norm = normalize_text(str(matrix[hdr_idx][qty_col_idx] or ""))
        explicit_qty_sold = any(
            tok in qty_header_norm for tok in ("vendid", "sold", "venta", "quantity", "cantidad", "cant")
        )

        has_sales = bool(
            ("quantity_sold" in s_map or "line_total" in s_map)
            and (
                explicit_sale_col
                or is_sale_sheet_name
                or ("vendid" in qty_header_norm or "sold" in qty_header_norm)
            )
        )
        has_products = bool(
            ("name" in p_map or "sku" in p_map)
            and (
                not has_sales
                or "initial_stock" in p_map
                or "cost_price" in p_map
                or "min_stock" in p_map
            )
        )

        if has_sales and not explicit_qty_sold and is_sale_sheet_name:
            p_map.pop("initial_stock", None)
            if "cost_price" not in p_map and "min_stock" not in p_map:
                has_products = False

        for row in matrix[hdr_idx + 1 :]:
            relevant_cells = [
                row[i]
                for i in set(p_map.values()) | set(s_map.values())
                if i < len(row) and row[i] is not None and str(row[i]).strip()
            ]
            if not relevant_cells:
                continue

            raw_name_text = _clean_unified_text(cell(row, p_map, "name"), 180)
            raw_sku = _clean_unified_text(cell(row, p_map, "sku"), 64).upper()
            if not raw_name_text and not raw_sku:
                continue
            if _is_ignored_summary_row(raw_name_text or raw_sku):
                continue

            cost_val = _normalize_unified_decimal(cell(row, p_map, "cost_price"), "0.01", "0")
            price_raw = cell(row, p_map, "sale_price")
            if price_raw is None:
                price_raw = cell(row, s_map, "unit_price")
            sale_price_val = _normalize_unified_decimal(price_raw, "0.01", "0")
            vat_raw = cell(row, p_map, "vat_rate")
            vat_val = (
                _normalize_unified_decimal(vat_raw, "0.01", "0")
                if vat_raw is not None
                else Decimal("0.00")
            )
            min_stock_val = _normalize_unified_decimal(cell(row, p_map, "min_stock"), "0.001", "2")
            cat_val = str(cell(row, p_map, "category") or "General")
            unit_val = str(cell(row, p_map, "unit") or "und")

            if has_products:
                stock_val = (
                    _normalize_unified_decimal(cell(row, p_map, "initial_stock"), "0.001", "0")
                    if "initial_stock" in p_map
                    else Decimal("0.000")
                )
                prod_entry = register_product(
                    sku_raw=raw_sku,
                    name_raw=raw_name_text,
                    category=cat_val,
                    unit=unit_val,
                    cost_price=cost_val,
                    sale_price=sale_price_val,
                    vat_rate=vat_val,
                    initial_stock=stock_val,
                    min_stock=min_stock_val,
                    sheet_name=sheet_name,
                )
                if sale_price_val > 0:
                    unit_price_samples[prod_entry["name"]].append(sale_price_val)

            if has_sales:
                qty_col_val = _normalize_unified_decimal(cell(row, s_map, "quantity_sold"), "0.001", "0")
                total_cell = _normalize_unified_decimal(cell(row, s_map, "line_total"), "0.01", "0")
                discount_val = _normalize_unified_decimal(cell(row, s_map, "discount"), "0.01", "0")
                parts = _split_raw_product_combo_items(raw_name_text or raw_sku, seen_canonical)
                if not parts:
                    continue
                if len(parts) == 1 and qty_col_val > 0:
                    parts = [(parts[0][0], qty_col_val)]

                unit_p_explicit = sale_price_val if sale_price_val > 0 else Decimal("0.00")
                if total_cell > 0:
                    line_val = total_cell
                elif len(parts) == 1 and unit_p_explicit > 0:
                    line_val = max(
                        Decimal("0.00"),
                        (parts[0][1] * unit_p_explicit - discount_val).quantize(Decimal("0.01")),
                    )
                else:
                    continue

                if line_val <= 0 and qty_col_val <= 0:
                    continue

                # Recolectar muestra de precio unitario base cuando la fila tiene 1 producto
                if len(parts) == 1:
                    cname, cqty = parts[0]
                    if cqty > 0 and line_val > 0:
                        implied_u = (line_val / cqty).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                        unit_price_samples[cname].append(implied_u)

                sale_ref = (
                    _clean_unified_text(cell(row, s_map, "sale_number"), 64) or f"EXC-{sale_seq:04d}"
                )
                sale_seq += 1
                pending_sale_rows.append(
                    {
                        "sale_reference": sale_ref,
                        "occurred_at": _normalize_unified_date(cell(row, s_map, "occurred_at")),
                        "raw_text": raw_name_text or raw_sku,
                        "forced_qty": qty_col_val if len(parts) == 1 and qty_col_val > 0 else None,
                        "line_value": line_val,
                        "discount": discount_val,
                        "customer_label": _clean_unified_text(
                            cell(row, s_map, "customer_label") or "Cliente Mostrador", 80
                        )
                        or "Cliente Mostrador",
                        "payment_method": _normalize_payment(cell(row, s_map, "payment_method")),
                        "sheet_name": sheet_name,
                        "sku_hint": raw_sku if len(parts) == 1 else "",
                        "cost_val": cost_val,
                        "vat_val": vat_val,
                        "min_stock_val": min_stock_val,
                        "cat_val": cat_val,
                        "unit_val": unit_val,
                    }
                )

    # Calcular precio unitario sugerido por producto (moda o mediana de muestras simples)
    known_unit_prices: dict[str, Decimal] = {}
    for p_name, samples in unit_price_samples.items():
        if not samples:
            continue
        counts = Counter(samples)
        top_freq = counts.most_common(1)[0][1]
        modes = [val for val, cnt in counts.items() if cnt == top_freq]
        if len(modes) == 1:
            known_unit_prices[p_name] = modes[0]
        else:
            med = Decimal(str(statistics.median([float(x) for x in samples]))).quantize(Decimal("0.01"))
            known_unit_prices[p_name] = med

    # Pasada 2: descomponer cada venta (incluyendo combos) y consolidar catálogo único
    sales_list: list[dict[str, Any]] = []
    total_sales_acc = Decimal("0.00")

    for pending in pending_sale_rows:
        raw_for_parse = pending["raw_text"]
        if pending["forced_qty"] is not None:
            canon_only = canonicalize_product_name(raw_for_parse, seen_canonical)
            items = parse_product_cell_and_combos(
                f"{canon_only} x{pending['forced_qty']}",
                pending["line_value"],
                known_unit_prices,
                seen_canonical,
            )
        else:
            items = parse_product_cell_and_combos(
                raw_for_parse,
                pending["line_value"],
                known_unit_prices,
                seen_canonical,
            )
        if not items:
            continue

        resolved_items: list[dict[str, Any]] = []
        summary_parts: list[str] = []
        for it in items:
            p_name = it["product_name"]
            base_sug = known_unit_prices.get(p_name, it["unit_price"])
            prod_entry = register_product(
                sku_raw=pending["sku_hint"] if len(items) == 1 else "",
                name_raw=p_name,
                category=pending["cat_val"],
                unit=pending["unit_val"],
                cost_price=pending["cost_val"],
                sale_price=base_sug,
                vat_rate=pending["vat_val"],
                initial_stock=Decimal("0.000"),
                min_stock=pending["min_stock_val"],
                sheet_name=pending["sheet_name"],
            )
            units_sold_by_name[prod_entry["name"]] += it["quantity"]
            q_fmt = (
                str(int(it["quantity"]))
                if it["quantity"] == it["quantity"].to_integral_value()
                else str(it["quantity"])
            )
            summary_parts.append(f"{prod_entry['name']} x{q_fmt}")
            resolved_items.append(
                {
                    "sku": prod_entry["sku"],
                    "product_name": prod_entry["name"],
                    "quantity": str(it["quantity"]),
                    "unit_price": str(it["unit_price"]),
                    "line_total": str(it["line_total"]),
                }
            )

        total_sales_acc += pending["line_value"]
        first_item = resolved_items[0]
        sales_list.append(
            {
                "sale_reference": pending["sale_reference"],
                "occurred_at": pending["occurred_at"],
                "sku": first_item["sku"],
                "product_name": first_item["product_name"],
                "products_summary": " + ".join(summary_parts),
                "quantity": first_item["quantity"],
                "unit_price": first_item["unit_price"],
                "unit_cost": str(products_by_key[first_item["sku"]]["cost_price"]),
                "vat_rate": str(products_by_key[first_item["sku"]]["vat_rate"]),
                "discount": str(pending["discount"]),
                "line_total": str(pending["line_value"]),
                "customer_label": pending["customer_label"],
                "payment_method": pending["payment_method"],
                "sheet_name": pending["sheet_name"],
                "items": resolved_items,
            }
        )

    serialized_products = []
    for p in products_by_key.values():
        suggested_sale_p = known_unit_prices.get(p["name"], p["sale_price"])
        if p["sale_price"] == Decimal("0.00") and suggested_sale_p > 0:
            p["sale_price"] = suggested_sale_p
        sold_total = units_sold_by_name.get(p["name"], Decimal("0.000"))
        serialized_products.append(
            {
                **p,
                "cost_price": str(p["cost_price"]),
                "sale_price": str(p["sale_price"]),
                "vat_rate": str(p["vat_rate"]),
                "initial_stock": str(p["initial_stock"]),
                "min_stock": str(p["min_stock"]),
                "units_sold": str(sold_total.quantize(Decimal("0.001"))),
            }
        )

    total_str = str(total_sales_acc.quantize(Decimal("0.01")))
    return {
        "filename": filename,
        "sheets": [name for name, _ in sheets_matrices],
        "products_count": len(serialized_products),
        "sales_count": len(sales_list),
        "total_sales_cop": total_str,
        "summary_text": (
            f"Análisis de tu archivo completado: Se encontraron {len(serialized_products)} productos "
            f"y {len(sales_list)} ventas registradas"
        ),
        "products": serialized_products,
        "sales": sales_list,
    }
