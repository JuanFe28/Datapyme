"""Tests Unitarios del Motor Detallado de Pérdidas, Ganancias y Rentabilidad por Producto."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.analytics.profitability import compute_pure_profitability


def test_compute_pure_profitability_pnl_losses_and_rankings():
    now = datetime(2026, 11, 15, 12, 0, tzinfo=UTC)
    products = [
        {
            "id": "p1",
            "sku": "FER-001",
            "name": "Taladro Percutor",
            "category": "Herramientas",
            "unit": "und",
            "cost_price": Decimal("100000.00"),
            "stock_qty": Decimal("5.000"),
            "image_url": None,
        },
        {
            "id": "p2",
            "sku": "FER-002",
            "name": "Cemento Gris 50kg",
            "category": "Construcción",
            "unit": "bulto",
            "cost_price": Decimal("30000.00"),
            "stock_qty": Decimal("10.000"),
            "image_url": None,
        },
        {
            "id": "p3",
            "sku": "FER-003",
            "name": "Llave Stillson 24p",
            "category": "Herramientas",
            "unit": "und",
            "cost_price": Decimal("50000.00"),
            "stock_qty": Decimal("4.000"),
            "image_url": None,
        },
    ]

    sales = [
        {
            "id": "s1",
            "status": "completed",
            "occurred_at": now - timedelta(days=2),
            "subtotal": Decimal("300000.00"),
            "discount_total": Decimal("0.00"),
            "cogs_total": Decimal("200000.00"),
        },
        {
            # Venta bajo costo (descuento excesivo): costo 30000*2 = 60000, venta neta 50000
            "id": "s2",
            "status": "completed",
            "occurred_at": now - timedelta(days=5),
            "subtotal": Decimal("60000.00"),
            "discount_total": Decimal("10000.00"),
            "cogs_total": Decimal("60000.00"),
        },
        {
            # Anulada: no debe sumar
            "id": "s_void",
            "status": "voided",
            "occurred_at": now - timedelta(days=1),
            "subtotal": Decimal("999999.00"),
            "discount_total": Decimal("0.00"),
            "cogs_total": Decimal("500000.00"),
        },
    ]

    sale_items = [
        {
            "sale_id": "s1",
            "product_id": "p1",
            "quantity": Decimal("2.000"),
            "unit_price": Decimal("150000.00"),
            "discount": Decimal("0.00"),
            "unit_cost_snapshot": Decimal("100000.00"),
        },
        {
            "sale_id": "s2",
            "product_id": "p2",
            "quantity": Decimal("2.000"),
            "unit_price": Decimal("30000.00"),
            "discount": Decimal("10000.00"),
            "unit_cost_snapshot": Decimal("30000.00"),
        },
        {
            "sale_id": "s_void",
            "product_id": "p3",
            "quantity": Decimal("10.000"),
            "unit_price": Decimal("100000.00"),
            "discount": Decimal("0.00"),
            "unit_cost_snapshot": Decimal("50000.00"),
        },
    ]

    shrinkage_movements = [
        {
            "product_id": "p2",
            "movement_type": "adjustment_out",
            "quantity": Decimal("-1.000"),
            "unit_cost": Decimal("30000.00"),
            "occurred_at": now - timedelta(days=3),
        }
    ]

    result = compute_pure_profitability(
        products=products,
        sales=sales,
        sale_items=sale_items,
        shrinkage_movements=shrinkage_movements,
        period_days=30,
        now=now,
    )

    pnl = result["pnl"]
    # Net revenue = 300000 + (60000 - 10000) = 350000.00
    assert pnl["gross_sales_without_vat"] == "360000.00"
    assert pnl["discount_total"] == "10000.00"
    assert pnl["net_revenue"] == "350000.00"
    assert pnl["cogs_total"] == "260000.00"
    assert pnl["gross_profit"] == "90000.00"
    assert pnl["shrinkage_loss_cop"] == "30000.00"
    assert pnl["below_cost_loss_cop"] == "10000.00"
    assert pnl["total_losses_cop"] == "40000.00"
    # Net profit after shrinkage = 90000 - 30000 = 60000.00 (below-cost ya está reflejado en gross_profit)
    assert pnl["net_profit_after_losses_cop"] == "60000.00"
    # p3 tiene 4 unidades a 50000 = 200000 inmovilizado sin ventas en 30D
    assert pnl["immobilized_capital_30d_cop"] == "200000.00"

    # Top selling: p1 liderando por ganancia 100000
    top = result["top_selling_products"]
    assert len(top) == 2
    assert top[0]["sku"] == "FER-001"
    assert top[0]["profit_cop"] == "100000.00"

    # Least selling / losses: incluye p3 con 0 ventas y p2 con merma/bajo costo
    least = result["least_selling_and_loss_products"]
    least_skus = {item["sku"]: item for item in least}
    assert "FER-003" in least_skus
    assert least_skus["FER-003"]["units_sold"] == "0.000"
    assert least_skus["FER-003"]["last_sale_label"] == "Sin ventas registradas"
    assert least_skus["FER-003"]["stock_value_cop"] == "200000.00"
    assert "FER-002" in least_skus
    assert least_skus["FER-002"]["diagnosis_severity"] == "danger"

    # Series temporal para 30D debe tener 4 cubetas semanales coherentes
    series = result["series"]
    assert len(series["labels"]) == 4
    assert len(series["revenue"]) == 4
    assert sum(series["revenue"]) == 350000.0


def test_sales_and_shrinkage_at_reporting_boundary_match_chart_totals():
    now = datetime(2026, 11, 18, 18, tzinfo=UTC)
    cutoff = now - timedelta(days=7)
    result = compute_pure_profitability(
        products=[],
        sales=[
            {"id": "first", "occurred_at": cutoff, "subtotal": "100", "cogs_total": "40"},
            {"id": "last", "occurred_at": now, "subtotal": "200", "cogs_total": "80"},
            {"id": "old", "occurred_at": cutoff - timedelta(seconds=1), "subtotal": "500"},
        ],
        sale_items=[],
        shrinkage_movements=[
            {
                "movement_type": "adjustment_out",
                "product_id": "test",
                "quantity": "-1",
                "unit_cost": "20",
                "occurred_at": when,
            }
            for when in (cutoff, cutoff - timedelta(seconds=1))
        ],
        period_days=7,
        now=now,
    )

    assert result["confirmed_sales_count"] == 2
    assert result["pnl"]["net_revenue"] == "300.00"
    assert result["pnl"]["shrinkage_loss_cop"] == "20.00"
    assert result["series"]["revenue"] == [100.0, 0.0, 0.0, 0.0, 0.0, 0.0, 200.0]
    assert sum(result["series"]["losses_and_costs"]) == 140
