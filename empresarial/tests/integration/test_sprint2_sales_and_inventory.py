"""Tests de Integración de Sprint 2: Catálogo, Kardex Inmutable, Ventas Atómicas y Alertas de Stock (Act. 3.3)."""

from decimal import Decimal

import pytest
from sqlalchemy import func, text
from sqlalchemy.exc import IntegrityError, InternalError, OperationalError


def _register_company(client, email="gerencia@ferrecabecera.co", name="Ferretería Cabecera S.A.S."):
    resp = client.post(
        "/api/auth/register",
        json={
            "legal_name": name,
            "tax_status": "responsible",
            "subsector": "ferreteria_hogar",
            "size": "pequena",
            "email": email,
            "full_name": "Carlos Mendoza",
            "password": "FerreCabecera2026!Secure",
            "accept_data_policy": True,
            "accept_terms_mvp": True,
            "accept_aggregate_stats": True,
            "diagnosis": {
                "M10": ["Diferencias en inventario"],
                "M12": ["Existencias y alertas"],
                "M17": "Inventarios y existencias",
                "M07": ["Hojas de cálculo"],
                "M08": ["Hojas de cálculo"],
                "M13": "No",
                "M15": ["Precio"],
            },
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["access_token"], resp.json()["tenant_id"]


def test_kardex_reconciliation_atomic_sales_and_void_reversal(client):
    """
    Verifica:
    1. Creación de productos con stock inicial y movimiento initial_load en kardex.
    2. Registro de entradas/ajustes y bloqueo de stock negativo (409).
    3. Venta operativa atómica con cálculo exacto en Decimal (subtotal, IVA, total, COGS).
    4. Rollback atómico cuando un segundo ítem de la venta supera el stock disponible.
    5. Anulación de venta (void) con reversa en kardex y reconciliación SUM(movements) == stock_qty.
    6. Inmutabilidad de inventory_movements ante UPDATE/DELETE directo.
    """
    token, tenant_id = _register_company(client)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Crear dos productos en el catálogo
    p1_res = client.post(
        "/api/products",
        headers=headers,
        json={
            "sku": "ARG-50KG",
            "name": "Cemento Gris Argos 50kg",
            "category": "Obra Gris",
            "unit": "bulto",
            "cost_price": "28500.00",
            "sale_price": "34900.00",
            "vat_rate": "19.00",
            "initial_stock": "60.000",
            "min_stock": "20.000",
        },
    )
    assert p1_res.status_code == 201, p1_res.text
    p1 = p1_res.json()
    assert Decimal(p1["stock_qty"]) == Decimal("60.000")

    p2_res = client.post(
        "/api/products",
        headers=headers,
        json={
            "sku": "PAV-PVC-3IN",
            "name": "Tubo PVC Sanitario 3 pulg Pavco",
            "category": "Tubería y PVC",
            "unit": "und",
            "cost_price": "48000.00",
            "sale_price": "59900.00",
            "vat_rate": "19.00",
            "initial_stock": "10.000",
            "min_stock": "15.000",
        },
    )
    assert p2_res.status_code == 201, p2_res.text
    p2 = p2_res.json()

    # 2. Registrar entrada de compra (+15 bultos a p1) y rechazar salida que deje stock negativo
    mov_ok = client.post(
        "/api/inventory/movements",
        headers=headers,
        json={
            "product_id": p1["id"],
            "movement_type": "purchase_in",
            "quantity": "15.000",
            "unit_cost": "28500.00",
            "reason": "Factura Proveedor FE-9821 Argos",
        },
    )
    assert mov_ok.status_code == 201, mov_ok.text
    assert Decimal(mov_ok.json()["new_stock_qty"]) == Decimal("75.000")

    mov_bad = client.post(
        "/api/inventory/movements",
        headers=headers,
        json={
            "product_id": p2["id"],
            "movement_type": "adjustment_out",
            "quantity": "-25.000",
            "reason": "Intento de merma mayor al stock",
        },
    )
    assert mov_bad.status_code == 409

    # 3. Rollback atómico: intentar vender 5 de p1 (sí hay) y 50 de p2 (solo hay 10)
    atomic_fail = client.post(
        "/api/sales",
        headers=headers,
        json={
            "customer_label": "Contratista Obra Civil #88",
            "payment_method": "transfer",
            "items": [
                {"product_id": p1["id"], "quantity": "5.000", "discount": "0.00"},
                {"product_id": p2["id"], "quantity": "50.000", "discount": "0.00"},
            ],
        },
    )
    assert atomic_fail.status_code == 409
    # Verificar que el stock de p1 sigue intacto en 75.000 tras el fallo del segundo ítem
    p1_check = client.get(f"/api/products/{p1['id']}", headers=headers).json()
    assert Decimal(p1_check["stock_qty"]) == Decimal("75.000")

    # 4. Venta exitosa de 5 bultos de p1 y 2 tubos de p2
    sale_res = client.post(
        "/api/sales",
        headers=headers,
        json={
            "customer_label": "Constructora Bucaramanga S.A.S.",
            "payment_method": "transfer",
            "items": [
                {"product_id": p1["id"], "quantity": "5.000", "discount": "4500.00"},
                {"product_id": p2["id"], "quantity": "2.000", "discount": "0.00"},
            ],
        },
    )
    assert sale_res.status_code == 201, sale_res.text
    sale = sale_res.json()
    assert sale["sale_number"] == 1
    assert sale["status"] == "completed"
    # p1: 5 * 34900 = 174500 - 4500 = 170000; p2: 2 * 59900 = 119800 -> subtotal = 289800.00
    assert Decimal(sale["subtotal"]) == Decimal("294300.00")
    assert Decimal(sale["discount_total"]) == Decimal("4500.00")
    # IVA 19% sobre (170000 + 119800 = 289800) = 55062.00 -> total = 344862.00
    assert Decimal(sale["vat_total"]) == Decimal("55062.00")
    assert Decimal(sale["total"]) == Decimal("344862.00")
    # COGS: 5 * 28500 (142500) + 2 * 48000 (96000) = 238500.00
    assert Decimal(sale["cogs_total"]) == Decimal("238500.00")

    # Stock descontado: p1 = 70, p2 = 8
    assert Decimal(
        client.get(f"/api/products/{p1['id']}", headers=headers).json()["stock_qty"]
    ) == Decimal("70.000")
    assert Decimal(
        client.get(f"/api/products/{p2['id']}", headers=headers).json()["stock_qty"]
    ) == Decimal("8.000")

    # 5. Anular la venta y comprobar reversa atómica en kardex
    void_res = client.post(f"/api/sales/{sale['id']}/void", headers=headers)
    assert void_res.status_code == 200, void_res.text
    assert void_res.json()["status"] == "voided"
    assert Decimal(
        client.get(f"/api/products/{p1['id']}", headers=headers).json()["stock_qty"]
    ) == Decimal("75.000")
    assert Decimal(
        client.get(f"/api/products/{p2['id']}", headers=headers).json()["stock_qty"]
    ) == Decimal("10.000")

    # 6. Reconciliación matemática Kardex == stock_qty e inmutabilidad por trigger
    from app.core.models import InventoryMovement, Product

    with client.app.state.Session() as db:
        for prod_id in (p1["id"], p2["id"]):
            prod = db.get(Product, prod_id)
            kardex_sum = (
                db.query(func.sum(InventoryMovement.quantity))
                .filter_by(tenant_id=tenant_id, product_id=prod_id)
                .scalar()
            )
            assert Decimal(str(prod.stock_qty)) == Decimal(str(kardex_sum))

        with pytest.raises((OperationalError, IntegrityError, InternalError)):
            db.execute(text("DELETE FROM inventory_movements"))
            db.commit()
        db.rollback()


def test_inventory_alerts_classification(client):
    """Verifica detección de agotados, riesgo de quiebre y sobreinventario."""
    token, _ = _register_company(client, email="alertas@ferrecabecera.co")
    headers = {"Authorization": f"Bearer {token}"}

    # Agotado (stock = 0, min = 10)
    client.post(
        "/api/products",
        headers=headers,
        json={
            "sku": "SKU-OUT",
            "name": "Producto Agotado",
            "category": "General",
            "cost_price": "1000",
            "sale_price": "1500",
            "initial_stock": "0",
            "min_stock": "10",
        },
    )
    # Riesgo de quiebre (stock = 5 <= min = 10)
    client.post(
        "/api/products",
        headers=headers,
        json={
            "sku": "SKU-RISK",
            "name": "Producto en Riesgo",
            "category": "General",
            "cost_price": "1000",
            "sale_price": "1500",
            "initial_stock": "5",
            "min_stock": "10",
        },
    )
    # Sobreinventario (stock = 40 >= min * 3 = 30)
    client.post(
        "/api/products",
        headers=headers,
        json={
            "sku": "SKU-OVER",
            "name": "Producto Sobrestockeado",
            "category": "General",
            "cost_price": "1000",
            "sale_price": "1500",
            "initial_stock": "40",
            "min_stock": "10",
        },
    )

    alerts = client.get("/api/inventory/alerts", headers=headers).json()
    assert [x["sku"] for x in alerts["out_of_stock"]] == ["SKU-OUT"]
    assert [x["sku"] for x in alerts["stockout_risk"]] == ["SKU-RISK"]
    assert [x["sku"] for x in alerts["overstock"]] == ["SKU-OVER"]


def test_perfumery_ml_g_l_units_sale_dashboard_csv_and_import(client):
    """Act. 3.8: Verifica creación, venta, tabla, comprobante, exportación CSV e importación en ml, g y l."""
    token, _ = _register_company(
        client, email="perfumeria@esencias.co", name="Perfumería Esencias Bucaramanga"
    )
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Crear producto de perfumería en mililitros (100 ml iniciales)
    prod_res = client.post(
        "/api/products",
        headers=headers,
        json={
            "sku": "PERF-100ML",
            "name": "Esencia Vainilla Premium",
            "category": "Perfumería",
            "unit": "ml",
            "cost_price": "900.00",
            "sale_price": "1800.00",
            "vat_rate": "0.00",
            "initial_stock": "100",
            "min_stock": "20",
        },
    )
    assert prod_res.status_code == 201, prod_res.text
    prod = prod_res.json()
    assert prod["unit"] == "ml"
    assert Decimal(prod["stock_qty"]) == Decimal("100.000")

    # 2. Vender 5 ml -> stock restante exacto = 95 ml
    sale_res = client.post(
        "/api/sales",
        headers=headers,
        json={
            "customer_label": "Cliente Mostrador",
            "payment_method": "cash",
            "items": [{"product_id": prod["id"], "quantity": "5"}],
        },
    )
    assert sale_res.status_code == 201, sale_res.text
    sale_data = sale_res.json()
    assert Decimal(sale_data["total"]) == Decimal("9000.00")
    assert sale_data["items"][0]["product_unit"] == "ml"
    assert Decimal(sale_data["items"][0]["quantity"]) == Decimal("5.000")

    updated = client.get(f"/api/products/{prod['id']}", headers=headers).json()
    assert Decimal(updated["stock_qty"]) == Decimal("95.000")
    assert updated["unit"] == "ml"

    # 3. Verificar en dashboard HTML el selector (ml, g, l + existentes) y stock "95 ml"
    dash = client.get("/dashboard", headers={**headers, "Accept": "text/html"})
    assert dash.status_code == 200
    assert '<option value="ml">Mililitro (ml)</option>' in dash.text
    assert '<option value="g">Gramo (g)</option>' in dash.text
    assert '<option value="l">Litro (L)</option>' in dash.text
    assert '<option value="galon">Galón</option>' in dash.text
    assert "95 ml" in dash.text

    # 4. Verificar unidad en exportación CSV Habeas Data
    csv_export = client.get("/api/me/export?format=csv", headers=headers)
    assert csv_export.status_code == 200
    assert "unit,ml" in csv_export.text

    # 5. Verificar normalización de textos en importación CSV ("mililitros", "gramos", "litros")
    csv_payload = (
        "sku,name,category,unit,cost_price,sale_price,vat_rate,initial_stock,min_stock\n"
        "ES-01,Extracto Rosa,Perfumería,mililitros,800,1600,0,50,10\n"
        "CR-01,Crema Base,Cosmética,gramos,300,700,0,250,50\n"
        "AL-01,Alcohol Perfumería,Insumos,litros,15000,25000,0,2.5,0.5\n"
    ).encode()
    imp = client.post(
        "/api/imports/products?mode=commit",
        headers=headers,
        files={"file": ("perfumeria.csv", csv_payload, "text/csv")},
    )
    assert imp.status_code == 201, imp.text
    by_sku = {p["sku"]: p for p in client.get("/api/products", headers=headers).json()}
    assert by_sku["ES-01"]["unit"] == "ml"
    assert by_sku["CR-01"]["unit"] == "g"
    assert by_sku["AL-01"]["unit"] == "l"
