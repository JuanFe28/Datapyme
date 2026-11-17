"""Tests Unitarios del Motor Determinista 'Plan de Acción Comercial de la Semana'."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.analytics.action_advisor import compute_weekly_action_plan


def test_action_advisor_restock_cash_release_and_goal_thermometer():
    now = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)
    products = [
        {
            "id": "p_fast",
            "sku": "CAF-001",
            "name": "Café Especial 500g",
            "unit": "und",
            "cost_price": Decimal("12000.00"),
            "sale_price": Decimal("24000.00"),
            "stock_qty": Decimal("4.000"),
            "min_stock": Decimal("6.000"),
            "is_active": True,
        },
        {
            "id": "p_stag",
            "sku": "TER-002",
            "name": "Termo Acero Lento",
            "unit": "und",
            "cost_price": Decimal("30000.00"),
            "sale_price": Decimal("50000.00"),
            "stock_qty": Decimal("5.000"),
            "min_stock": Decimal("2.000"),
            "is_active": True,
        },
        {
            "id": "p_tight_margin",
            "sku": "AZU-003",
            "name": "Azúcar Económica",
            "unit": "kg",
            "cost_price": Decimal("4000.00"),
            "sale_price": Decimal("4300.00"),
            "stock_qty": Decimal("10.000"),
            "min_stock": Decimal("2.000"),
            "is_active": True,
        },
    ]

    sales = [
        {
            "id": "s1",
            "status": "completed",
            "occurred_at": now - timedelta(days=2),
            "subtotal": Decimal("720000.00"),
            "discount_total": Decimal("0.00"),
        }
    ]
    sale_items = [{"sale_id": "s1", "product_id": "p_fast", "quantity": Decimal("30.000")}]
    forecast_payload = {
        "forecast_ols": [{"period": "Mes+1", "value": "1200000.00"}],
        "historical": [{"period": "Mes0", "value": "900000.00"}],
    }

    plan = compute_weekly_action_plan(
        products=products,
        sales=sales,
        sale_items=sale_items,
        forecast_payload=forecast_payload,
        now=now,
    )

    # 1. Reabastecimiento: daily_rate = 1.0/día -> 4 días restantes; sugiere 15 + 6 - 4 = 17 und
    restock = plan["restock_suggestions"]
    assert len(restock) == 1
    assert restock[0]["sku"] == "CAF-001"
    assert restock[0]["days_remaining"] == 4
    assert restock[0]["suggested_units"] == 17
    assert restock[0]["investment_cop"] == "204000.00"

    # 2. Simulador de liberación de efectivo:
    # TER-002 (5 und): 20% desc de 50000 = 40000 (>= 1.05 * 30000 = 31500) -> 200000
    # AZU-003 (10 und): 20% desc de 4300 = 3440 < 1.05 * 4000 (4200) -> protegido al piso 4200 -> 42000
    sim = plan["cash_release_simulator"]
    assert sim["stagnant_products_count"] == 2
    sc20 = sim["scenarios"]["20"]
    assert sc20["protected_at_cost_floor"] == 1
    assert Decimal(sc20["cash_released_cop"]) == Decimal("242000.00")
    assert Decimal(sc20["retained_profit_cop"]) > Decimal("0.00")

    # 3. Termómetro de Meta Mensual: 720000 / 1200000 = 60.00%
    goal = plan["monthly_goal_thermometer"]
    assert goal["current_month_revenue_cop"] == "720000.00"
    assert goal["target_revenue_cop"] == "1200000.00"
    assert goal["remaining_cop"] == "480000.00"
    assert goal["progress_pct"] == "60.00"
