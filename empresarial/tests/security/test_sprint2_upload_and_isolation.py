"""Tests de Seguridad Multi-Tenant de Ventas/Inventario y Sanitización OWASP de CSV/XLSX (Act. 3.3)."""
import io
from decimal import Decimal

import openpyxl


def _register_tenant(client, email: str, name: str):
    resp = client.post(
        "/api/auth/register",
        json={
            "legal_name": name,
            "subsector": "ferreteria_hogar",
            "size": "pequena",
            "email": email,
            "full_name": "Admin PyME",
            "password": "PasswordSeguro2026!",
            "accept_data_policy": True,
            "accept_terms_mvp": True,
            "accept_aggregate_stats": True,
            "diagnosis": {
                "M10": ["Diferencias en inventario"],
                "M12": ["Existencias y alertas"],
                "M17": "Inventarios y existencias",
            },
        },
    )
    assert resp.status_code == 201
    return resp.json()["access_token"], resp.json()["tenant_id"]


def test_strict_cross_tenant_isolation_on_products_sales_and_movements(client):
    """Un usuario de la PyME A jamás puede leer, modificar, mover stock ni vender productos de la PyME B."""
    tok_a, _ = _register_tenant(client, "pyme_a@test.co", "PyME A Comercial S.A.S.")
    tok_b, _ = _register_tenant(client, "pyme_b@test.co", "PyME B Comercial S.A.S.")
    hdr_a = {"Authorization": f"Bearer {tok_a}"}
    hdr_b = {"Authorization": f"Bearer {tok_b}"}

    # PyME B crea un producto y una venta
    prod_b = client.post(
        "/api/products",
        headers=hdr_b,
        json={
            "sku": "B-SECRET-01",
            "name": "Producto Exclusivo B",
            "category": "Reserva",
            "cost_price": "10000",
            "sale_price": "20000",
            "initial_stock": "50",
            "min_stock": "5",
        },
    ).json()

    sale_b = client.post(
        "/api/sales",
        headers=hdr_b,
        json={
            "customer_label": "Cliente B",
            "payment_method": "cash",
            "items": [{"product_id": prod_b["id"], "quantity": "2", "discount": "0"}],
        },
    ).json()

    # PyME A lista sus productos y ventas -> vacío (0 filtraciones de B)
    assert client.get("/api/products", headers=hdr_a).json() == []
    assert client.get("/api/sales", headers=hdr_a).json() == []

    # PyME A intenta acceder o manipular recursos de PyME B -> 404 en el 100 % de los casos
    assert client.get(f"/api/products/{prod_b['id']}", headers=hdr_a).status_code == 404
    assert (
        client.patch(
            f"/api/products/{prod_b['id']}",
            headers=hdr_a,
            json={"sale_price": "1.00"},
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/api/inventory/movements",
            headers=hdr_a,
            json={
                "product_id": prod_b["id"],
                "movement_type": "adjustment_out",
                "quantity": "-10",
                "reason": "Sabotaje cruzado",
            },
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/api/sales",
            headers=hdr_a,
            json={
                "customer_label": "Intento Cruzado",
                "payment_method": "cash",
                "items": [{"product_id": prod_b["id"], "quantity": "1", "discount": "0"}],
            },
        ).status_code
        == 404
    )
    assert client.get(f"/api/sales/{sale_b['id']}", headers=hdr_a).status_code == 404
    assert client.post(f"/api/sales/{sale_b['id']}/void", headers=hdr_a).status_code == 404


def test_csv_and_xlsx_bulk_imports_with_colombian_numbers_and_formula_sanitization(client):
    """
    Verifica:
    1. Importación CSV de productos con números en formato colombiano ("28.500,50") y neutralización
       de inyección de fórmulas (=CMD, +SUM, @malicioso).
    2. Importación Excel (.xlsx) de histórico de ventas descontando stock atómicamente.
    3. Rechazo de extensiones peligrosas (.xlsm).
    """
    tok, _ = _register_tenant(client, "import@ferre.co", "Ferretería Importadora S.A.S.")
    headers = {"Authorization": f"Bearer {tok}"}

    # 1. Rechazar archivos .xlsm con macros
    bad_ext = client.post(
        "/api/imports/products?mode=preview",
        headers=headers,
        files={"file": ("catalogo.xlsm", b"PK\x03\x04fake", "application/vnd.ms-excel")},
    )
    assert bad_ext.status_code == 422

    # 2. Importar catálogo CSV con formato es-CO e intento de Formula Injection en el nombre
    csv_content = (
        "sku,name,category,unit,cost_price,sale_price,vat_rate,initial_stock,min_stock\n"
        'ARG-50KG,"=CMD|\' /C calc\'!A0 Cemento Argos",Obra Gris,bulto,"28.500,00","34.900,00",19,100,20\n'
        'VIN-BL-1G,"+Pintura Viniltex Blanco",Pinturas,galon,"45.000,00","58.000,00",19,40,10\n'
        'BAD-ROW,"Producto Precio Negativo",Obra Gris,und,"-100","200",19,10,5\n'
    ).encode("utf-8-sig")

    preview_res = client.post(
        "/api/imports/products?mode=preview",
        headers=headers,
        files={"file": ("productos.csv", csv_content, "text/csv")},
    )
    assert preview_res.status_code == 200, preview_res.text
    prev_data = preview_res.json()
    assert prev_data["rows_total"] == 3
    assert prev_data["rows_ok"] == 2
    assert prev_data["rows_rejected"] == 1
    # En modo preview aún no se ha persistido nada
    assert client.get("/api/products", headers=headers).json() == []

    # Commit de las filas válidas
    commit_res = client.post(
        "/api/imports/products?mode=commit",
        headers=headers,
        files={"file": ("productos.csv", csv_content, "text/csv")},
    )
    assert commit_res.status_code == 201, commit_res.text
    prods = client.get("/api/products", headers=headers).json()
    assert len(prods) == 2
    by_sku = {p["sku"]: p for p in prods}
    # El prefijo peligroso '=' o '+' fue neutralizado para impedir ejecución de fórmulas
    assert not by_sku["ARG-50KG"]["name"].startswith("=")
    assert not by_sku["VIN-BL-1G"]["name"].startswith("+")
    assert Decimal(by_sku["ARG-50KG"]["cost_price"]) == Decimal("28500.00")
    assert Decimal(by_sku["ARG-50KG"]["stock_qty"]) == Decimal("100.000")

    # 3. Construir libro Excel (.xlsx) real en memoria para importar histórico de ventas
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Ventas"
    ws.append(["sku", "quantity", "unit_price", "discount", "payment_method", "customer_label"])
    ws.append(["ARG-50KG", "10", "34900", "0", "transfer", "=HYPERLINK('http://evil') Cliente 1"])
    ws.append(["VIN-BL-1G", "5", "58000", "10000", "cash", "Cliente Mostrador 2"])
    buf = io.BytesIO()
    wb.save(buf)
    xlsx_bytes = buf.getvalue()

    sales_imp = client.post(
        "/api/imports/sales?mode=commit",
        headers=headers,
        files={
            "file": (
                "ventas_historicas.xlsx",
                xlsx_bytes,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert sales_imp.status_code == 201, sales_imp.text
    imp_json = sales_imp.json()
    assert imp_json["rows_ok"] == 2
    assert imp_json["rows_rejected"] == 0

    # El stock de ARG-50KG bajó de 100 a 90 y VIN-BL-1G bajó de 40 a 35
    prods_after = {p["sku"]: p for p in client.get("/api/products", headers=headers).json()}
    assert Decimal(prods_after["ARG-50KG"]["stock_qty"]) == Decimal("90.000")
    assert Decimal(prods_after["VIN-BL-1G"]["stock_qty"]) == Decimal("35.000")
