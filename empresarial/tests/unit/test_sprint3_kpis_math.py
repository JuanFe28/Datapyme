"""Tests Unitarios Matemáticos de KPIs Comerciales y Clasificación Pareto (Sprint 3 — Act. 3.4)."""

from decimal import Decimal

from app.analytics.kpis import compute_pareto_and_stagnant, compute_pure_kpis


def test_compute_pure_kpis_decimal_precision_and_void_exclusion():
    sales_records = [
        {
            "status": "completed",
            "subtotal": Decimal("100000.00"),
            "discount_total": Decimal("10000.00"),
            "vat_total": Decimal("17100.00"),
            "total": Decimal("107100.00"),
            "cogs_total": Decimal("54000.00"),
        },
        {
            "status": "completed",
            "subtotal": Decimal("210000.00"),
            "discount_total": Decimal("0.00"),
            "vat_total": Decimal("39900.00"),
            "total": Decimal("249900.00"),
            "cogs_total": Decimal("126000.00"),
        },
        {
            # Venta anulada: debe excluirse de todos los agregados financieros
            "status": "voided",
            "subtotal": Decimal("500000.00"),
            "discount_total": Decimal("0.00"),
            "vat_total": Decimal("95000.00"),
            "total": Decimal("595000.00"),
            "cogs_total": Decimal("300000.00"),
        },
    ]

    result = compute_pure_kpis(
        sales_records=sales_records,
        inventory_value_at_cost=Decimal("90000.00"),
        period_days=30,
    )

    # Ingresos netos = (100000 - 10000) + 210000 = 300000.00
    assert result["net_revenue"] == "300000.00"
    assert result["cogs_total"] == "180000.00"
    # Utilidad bruta = 300000 - 180000 = 120000.00 (Margen = 40.00%)
    assert result["gross_profit"] == "120000.00"
    assert result["gross_margin_pct"] == "40.00"
    # Ticket promedio = 300000 / 2 ventas confirmadas = 150000.00
    assert result["avg_ticket"] == "150000.00"
    assert result["confirmed_sales_count"] == 2
    assert result["voided_sales_count"] == 1
    # Rotación de inventario = 180000 / 90000 = 2.00
    assert result["inventory_turnover"] == "2.00"
    # Días de cobertura = 90000 / (180000 / 30) = 15.00 días
    assert result["days_of_coverage"] == "15.00"


def test_compute_pure_kpis_zero_division_safety():
    empty_res = compute_pure_kpis(
        sales_records=[],
        inventory_value_at_cost=Decimal("0.00"),
        period_days=30,
    )
    assert empty_res["net_revenue"] == "0.00"
    assert empty_res["gross_margin_pct"] == "0.00"
    assert empty_res["avg_ticket"] == "0.00"
    assert empty_res["inventory_turnover"] == "0.00"
    assert empty_res["days_of_coverage"] is None


def test_pareto_star_vs_stagnant_classification():
    products = [
        {
            "id": "p1",
            "sku": "SKU-STAR",
            "name": "Cemento Gris",
            "category": "Obra",
            "stock_qty": Decimal(10),
            "cost_price": Decimal(25000),
        },
        {
            "id": "p2",
            "sku": "SKU-SEC",
            "name": "Arena Bulto",
            "category": "Obra",
            "stock_qty": Decimal(5),
            "cost_price": Decimal(10000),
        },
        {
            "id": "p3",
            "sku": "SKU-STAG",
            "name": "Taladro Especial",
            "category": "Herramienta",
            "stock_qty": Decimal(4),
            "cost_price": Decimal(200000),
        },
    ]
    sold_by_product = {
        "p1": {"units_sold": Decimal("20.000"), "net_revenue": Decimal("850000.00")},
        "p2": {"units_sold": Decimal("10.000"), "net_revenue": Decimal("150000.00")},
    }

    classified = compute_pareto_and_stagnant(products, sold_by_product)
    stars = classified["star_products"]
    stagnant = classified["stagnant_products"]

    assert len(stars) == 2
    assert stars[0]["sku"] == "SKU-STAR"
    assert stars[0]["revenue_share_pct"] == "85.00"
    assert stars[0]["is_pareto_80"] is True
    assert stars[1]["sku"] == "SKU-SEC"
    assert stars[1]["is_pareto_80"] is False

    assert len(stagnant) == 1
    assert stagnant[0]["sku"] == "SKU-STAG"
    assert stagnant[0]["immobilized_capital_cop"] == "800000.00"
