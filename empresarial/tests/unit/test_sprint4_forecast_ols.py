"""Tests Unitarios Estadísticos Golden para Regresión Lineal OLS y Promedios Móviles (Sprint 4 — Act. 3.5)."""

import pytest

from app.forecast.stats import MANDATORY_FDC124_DISCLAIMER, compute_ols_and_moving_averages


def test_golden_ols_and_moving_averages_exact_values():
    # Golden Test del Planning F-DC-124: y = [100, 120, 130, 150] para x = 1..4
    res = compute_ols_and_moving_averages([100, 120, 130, 150], horizon=2)

    assert res["status"] == "ok"
    assert res["beta_1"] == pytest.approx(16.0, abs=1e-6)
    assert res["beta_0"] == pytest.approx(85.0, abs=1e-6)
    assert res["r_squared"] == pytest.approx(0.984615, abs=1e-5)
    assert res["fit_quality_label"] == "alto"
    assert res["next_period_ols"] == pytest.approx(165.0, abs=1e-2)
    assert res["sma_3"] == pytest.approx(133.33, abs=1e-2)
    assert res["wma_3"] == pytest.approx(138.33, abs=1e-2)
    assert res["methodological_disclaimer"] == MANDATORY_FDC124_DISCLAIMER
    assert len(res["projections"]) == 2
    assert res["projections"][0]["ols_forecast"] == pytest.approx(165.0, abs=1e-2)
    assert res["projections"][1]["ols_forecast"] == pytest.approx(181.0, abs=1e-2)


def test_constant_and_decreasing_series_and_insufficient_data():
    # Serie constante: pendiente 0 y R^2 = 1.0 (sin división por cero)
    const_res = compute_ols_and_moving_averages([250, 250, 250])
    assert const_res["status"] == "ok"
    assert const_res["beta_1"] == pytest.approx(0.0, abs=1e-6)
    assert const_res["beta_0"] == pytest.approx(250.0, abs=1e-6)
    assert const_res["r_squared"] == pytest.approx(1.0, abs=1e-6)
    assert const_res["sma_3"] == pytest.approx(250.0, abs=1e-2)
    assert const_res["wma_3"] == pytest.approx(250.0, abs=1e-2)

    # Serie decreciente: y = [300, 200, 100] -> beta_1 = -100, beta_0 = 400
    dec_res = compute_ols_and_moving_averages([300, 200, 100])
    assert dec_res["beta_1"] == pytest.approx(-100.0, abs=1e-6)
    assert dec_res["beta_0"] == pytest.approx(400.0, abs=1e-6)
    assert dec_res["next_period_ols"] == pytest.approx(0.0, abs=1e-2)

    # Muestra insuficiente (n < 3)
    short_res = compute_ols_and_moving_averages([100, 120])
    assert short_res["status"] == "insufficient_data"
    assert short_res["minimum_periods_required"] == 3
    assert short_res["observed_periods"] == 2
    assert short_res["methodological_disclaimer"] == MANDATORY_FDC124_DISCLAIMER
