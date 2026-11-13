"""Tests de Integración de Sprint 3: Tablero Bento Grid Adaptativo y KPIs por Tenant (Act. 3.4)."""

from fastapi.testclient import TestClient

from app.main import create_app


def test_contrasting_tenants_render_distinct_bento_dashboard_and_isolated_kpis(tmp_path):
    db_file = tmp_path / "sprint3_bento.db"
    application = create_app(f"sqlite:///{db_file.as_posix()}", testing=True)

    with TestClient(application) as client:
        # Empresa A: Ferretería con dolores de inventario y cuaderno manual
        reg_a = client.post(
            "/api/auth/register",
            json={
                "legal_name": "Ferretería Cabecera S.A.S.",
                "tax_status": "responsible",
                "subsector": "Ferretería",
                "email": "ferreteria@cabecera.co",
                "full_name": "Carlos Mantilla",
                "password": "PasswordSeguro123!",
                "accept_data_policy": True,
                "accept_terms_mvp": True,
                "accept_aggregate_stats": True,
                "diagnosis": {
                    "M10": ["Diferencias en inventario", "No identifica fácilmente la rotación"],
                    "M12": ["Existencias y alertas", "Rotación de productos"],
                    "M17": "Inventarios y existencias",
                    "M07": ["Cuaderno o apuntes manuales"],
                    "M08": ["Manual"],
                    "M13": "No",
                    "M15": ["Falta de conocimientos tecnológicos"],
                },
            },
        )
        assert reg_a.status_code == 201
        tok_a = reg_a.json()["access_token"]
        headers_a = {"Authorization": f"Bearer {tok_a}"}

        # Empresa B: Boutique con enfoque en crecimiento de ventas y software previo
        reg_b = client.post(
            "/api/auth/register",
            json={
                "legal_name": "Boutique San Pío S.A.S.",
                "tax_status": "responsible",
                "subsector": "Moda",
                "email": "boutique@sanpio.co",
                "full_name": "Laura Serrano",
                "password": "PasswordSeguro123!",
                "accept_data_policy": True,
                "accept_terms_mvp": True,
                "accept_aggregate_stats": True,
                "diagnosis": {
                    "M10": ["Dificultad para analizar ventas", "Demora preparando informes"],
                    "M12": ["Ventas por periodo", "Comparación entre periodos"],
                    "M17": "Consulta de ventas e indicadores",
                    "M07": ["Facturación / punto de venta", "Software administrativo / ERP"],
                    "M08": ["Hojas de cálculo"],
                    "M13": "Sí",
                    "M15": ["Diariamente"],
                },
            },
        )
        assert reg_b.status_code == 201
        tok_b = reg_b.json()["access_token"]
        headers_b = {"Authorization": f"Bearer {tok_b}"}

        # Registrar producto y venta en Empresa A
        prod_a = client.post(
            "/api/products",
            headers=headers_a,
            json={
                "sku": "CEM-50",
                "name": "Cemento 50kg",
                "cost_price": "20000.00",
                "sale_price": "30000.00",
                "vat_rate": "19.00",
                "initial_stock": "10.000",
                "min_stock": "8.000",
            },
        ).json()
        client.post(
            "/api/sales",
            headers=headers_a,
            json={
                "items": [{"product_id": prod_a["id"], "quantity": "3.000"}],
            },
        )

        # Verificar KPIs de Empresa A vs Empresa B (aislamiento total)
        kpis_a = client.get("/api/kpis", headers=headers_a).json()
        kpis_b = client.get("/api/kpis", headers=headers_b).json()

        assert kpis_a["kpis"]["net_revenue"] == "90000.00"
        assert kpis_a["alerts_summary"]["stockout_risk"] == 1
        assert kpis_b["kpis"]["net_revenue"] == "0.00"
        assert kpis_b["alerts_summary"]["stockout_risk"] == 0

        # Verificar SSR HTML del Bento Grid Adaptativo en /dashboard
        html_a = client.get("/dashboard", headers=headers_a).text
        html_b = client.get("/dashboard", headers=headers_b).text

        assert 'data-primary-focus="inventory"' in html_a
        assert 'data-density="simple"' in html_a
        assert 'data-hero-widget="stock_alerts" data-hero-rank="1"' in html_a

        assert 'data-primary-focus="sales"' in html_b
        assert 'data-density="detailed"' in html_b
        assert 'data-hero-widget="sales_trend" data-hero-rank="1"' in html_b

        # Verificar conmutación manual a vista general
        html_a_general = client.get("/dashboard?view_mode=general", headers=headers_a).text
        assert 'data-view-mode="general"' in html_a_general
        assert "Volver a vista personalizada" in html_a_general
