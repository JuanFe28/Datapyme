"""
Servicio de Mapeo Inteligente de Excel Multi-Hoja y Diccionario de Sinónimos Comerciales (F-DC-124).
100% Python puro con openpyxl y csv, cero APIs externas.
"""

import io
import re
import unicodedata
import zipfile
from decimal import Decimal, InvalidOperation
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
        try:
            text_data = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            text_data = content.decode("latin-1")
        lines = [line for line in text_data.splitlines() if line.strip()]
        for line in lines[: MAX_SCAN_ROWS + 10]:
            parts = [p.strip() for p in re.split(r"[,;|\t]", line)]
            raw_matrix.append(parts)
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
        selected_sheet = target_sheet if (target_sheet and target_sheet in sheets) else sheets[0]
        ws = wb[selected_sheet]

        for row_idx, row in enumerate(ws.iter_rows(values_only=True), start=1):
            raw_matrix.append(list(row))
            if row_idx >= MAX_SCAN_ROWS + 10:
                break
        wb.close()

    # Detección inteligente de fila de encabezados en las primeras 15 filas
    best_row_idx = 0
    best_score = -1
    best_headers: list[str] = []

    all_synonyms = {syn for syn_list in SYNONYMS_MAP.values() for syn in syn_list}

    for row_idx, row in enumerate(raw_matrix[:MAX_SCAN_ROWS]):
        score = 0
        non_empty = [str(c or "").strip() for c in row if c is not None and str(c).strip()]
        if len(non_empty) < 2:
            continue
        for cell in non_empty:
            norm = normalize_text(cell)
            if norm in all_synonyms:
                score += 3
            elif any(syn in norm for syn in all_synonyms):
                score += 1
            elif re.search(r"[a-zA-Z]", norm):
                score += 0.2
        if score > best_score:
            best_score = score
            best_row_idx = row_idx
            best_headers = [str(c or "").strip() for c in row]

    if not best_headers:
        # Fallback a la primera fila con contenido
        for row_idx, row in enumerate(raw_matrix):
            if any(c is not None and str(c).strip() for c in row):
                best_row_idx = row_idx
                best_headers = [str(c or "").strip() for c in row]
                break

    # Filtrar columnas vacías al final
    while best_headers and not best_headers[-1]:
        best_headers.pop()

    # Generar nombres amigables si alguna columna intermedia está vacía
    columns = [h if h else f"Columna_{i + 1}" for i, h in enumerate(best_headers)]

    # Auto-Mapeo usando sinónimos comerciales
    suggested_mapping: dict[str, str | None] = {
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

    for field, synonyms in SYNONYMS_MAP.items():
        for col in columns:
            if col in assigned_cols:
                continue
            norm = normalize_text(col)
            # Coincidencia exacta o contenida
            if norm in synonyms or any(
                norm == syn or norm.startswith(syn + "_") or norm.endswith("_" + syn) for syn in synonyms
            ):
                suggested_mapping[field] = col
                assigned_cols.add(col)
                break

    # Extraer previsualización de 3 filas posteriores al encabezado
    sample_rows: list[dict[str, Any]] = []
    data_rows = raw_matrix[best_row_idx + 1 : best_row_idx + 4]

    for d_row in data_rows:
        if not any(c is not None and str(c).strip() for c in d_row):
            continue
        row_dict: dict[str, Any] = {}
        for c_idx, col_name in enumerate(columns):
            val = d_row[c_idx] if c_idx < len(d_row) else ""
            row_dict[col_name] = "" if val is None else str(val).strip()
        sample_rows.append(row_dict)

    return {
        "filename": filename,
        "sheets": sheets,
        "selected_sheet": selected_sheet,
        "header_row_index": best_row_idx + 1,  # 1-indexed para humanos
        "columns": columns,
        "suggested_mapping": suggested_mapping,
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
    raw_rows: list[list[Any]] = []

    if ext == ".csv":
        try:
            text_data = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            text_data = content.decode("latin-1")
        lines = [line for line in text_data.splitlines() if line.strip()]
        for line in lines:
            parts = [p.strip() for p in re.split(r"[,;|\t]", line)]
            raw_rows.append(parts)
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

        cost_clean = clean_currency_or_number_string(get_val(row_data, "cost_price"))
        sale_clean = clean_currency_or_number_string(get_val(row_data, "sale_price"))
        stock_clean = clean_currency_or_number_string(get_val(row_data, "initial_stock"))
        min_stock_clean = clean_currency_or_number_string(get_val(row_data, "min_stock"))

        try:
            cost_dec = Decimal(cost_clean).quantize(Decimal("0.01"))
        except (InvalidOperation, TypeError):
            cost_dec = Decimal("0.00")

        try:
            sale_dec = Decimal(sale_clean).quantize(Decimal("0.01"))
        except (InvalidOperation, TypeError):
            sale_dec = Decimal("0.00")

        try:
            stock_dec = Decimal(stock_clean).quantize(Decimal("0.001"))
        except (InvalidOperation, TypeError):
            stock_dec = Decimal("0.000")

        try:
            min_stock_dec = Decimal(min_stock_clean).quantize(Decimal("0.001"))
        except (InvalidOperation, TypeError):
            min_stock_dec = Decimal("0.000")

        parsed_products.append(
            {
                "sku": raw_sku.upper()[:64],
                "name": raw_name[:180],
                "category": category[:90],
                "unit": unit[:20],
                "cost_price": cost_dec,
                "sale_price": sale_dec,
                "vat_rate": Decimal("19.00"),
                "initial_stock": stock_dec,
                "min_stock": min_stock_dec,
                "row_number": row_num,
            }
        )

        if len(parsed_products) > MAX_ROWS_LIMIT:
            raise HTTPException(status_code=422, detail="El archivo supera el límite de 20.000 filas.")

    return parsed_products
