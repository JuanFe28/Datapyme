"""Tests de Integración E2E de Sprint 6: Seed Contrastante [DEMO-FDC125] y Flujo Completo F-DC-124."""
from fastapi.testclient import TestClient

from app.core.demo_seed import clear_contrast_demo_tenants, seed_contrast_demo_tenants
from app.main import create_app


def test_seed_and_clear_contrast_demo_tenants_e2e(tmp_path):
    db_file = tmp_path / "sprint6_e2e.db"
    application = create_app(f"sqlite:///{db_file.as_posix()}", testing=True)

    with TestClient(application) as client:
        with application.state.Session() as db:
            seeded = seed_contrast_demo_tenants(db)

        tok_a = seeded["empresa_a_inventario"]["access_token"]
        seeded["empresa_b_ventas"]["access_token"]
        seeded["empresa_c_predictivo"]["access_token"]
        tok_admin = seeded["superadmin"]["access_token"]

        # 1. Verificar prioridades adaptativas contrastantes entre Empresa A, B y C
        assert seeded["empresa_a_inventario"]["primary_focus"] == "inventory"
        assert seeded["empresa_b_ventas"]["primary_focus"] == "sales"
        assert seeded["empresa_c_predictivo"]["primary_focus"] == "predictive"

        # 2. Verificar pronóstico OLS + SMA-3 / WMA-3 en Empresa A (períodos históricos sembrados)
        fc_a = client.get(
            "/api/forecast?metric=net_revenue&horizon=2",
            headers={"Authorization": f"Bearer {tok_a}"},
        ).json()
        assert fc_a["status"] == "ok"
        assert fc_a["observed_periods"] >= 4
        assert fc_a["beta_1"] > 0
        assert fc_a["r_squared"] > 0.70
        assert "Regresión Lineal Simple por Mínimos Cuadrados Ordinarios (OLS)" in fc_a["methodological_disclaimer"]

        # 3. Verificar Telemetría SuperAdmin con las 3 empresas demo activas (k = 3) y al menos 40 ventas
        impact = client.get(
            "/api/admin/impact",
            headers={"Authorization": f"Bearer {tok_admin}"},
        ).json()
        assert impact["global"]["active_tenants"] == 3
        assert impact["global"]["is_suppressed"] is False
        assert impact["global"]["sales_count"] >= 40

        # 4. Limpiar empresas demo y verificar que quedan 0 empresas demo activas
        with application.state.Session() as db:
            cleared = clear_contrast_demo_tenants(db)
        assert cleared["demo_tenants_removed"] == 3
