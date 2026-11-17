"""Pruebas opcionales contra PostgreSQL local dedicado, nunca contra participantes."""

import os
import subprocess
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import sql
from test_company_tax import account

from app.main import create_app

pytestmark = pytest.mark.skipif(
    os.getenv("DATAPYME_LOCAL_PG_QA") != "1",
    reason="Requiere PostgreSQL sintético dedicado en 127.0.0.1:55439",
)


def new_database():
    name = "datapyme_qa_" + uuid.uuid4().hex[:14]
    with psycopg.connect(
        "host=127.0.0.1 port=55439 user=datapyme_qa dbname=postgres", autocommit=True
    ) as db:
        db.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    return name, f"postgresql+psycopg://datapyme_qa@127.0.0.1:55439/{name}"


@pytest.fixture
def pgclient():
    _, url = new_database()
    with TestClient(create_app(url, testing=True)) as client:
        yield client


def setup_stock(client):
    h = account(client)
    assert (
        client.put(
            "/api/company/tax",
            headers=h,
            json={
                "status": "responsible",
                "expected_revision": 0,
                "reason": "Prueba PostgreSQL sintética",
            },
        ).status_code
        == 200
    )
    p = client.post(
        "/api/products",
        headers=h,
        json={
            "sku": "PG1",
            "name": "QA PostgreSQL",
            "cost_price": "60",
            "sale_price": "100",
            "vat_rate": "19",
            "initial_stock": "5",
        },
    ).json()
    return h, p


def test_postgres_concurrent_sales_and_voids_preserve_stock(pgclient):
    h, p = setup_stock(pgclient)

    def sell(_):
        return pgclient.post(
            "/api/sales", headers=h, json={"items": [{"product_id": p["id"], "quantity": "4"}]}
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(sell, range(2)))
    assert sorted(r.status_code for r in results) == [201, 409]
    assert pgclient.get("/api/products/" + p["id"], headers=h).json()["stock_qty"] == "1.000"
    sale = next(r.json() for r in results if r.status_code == 201)
    assert sale["total"] == "476.00"

    def undo(_):
        return pgclient.post("/api/sales/" + sale["id"] + "/void", headers=h)

    with ThreadPoolExecutor(max_workers=2) as pool:
        voids = list(pool.map(undo, range(2)))
    assert sorted(r.status_code for r in voids) == [200, 409]
    assert pgclient.get("/api/products/" + p["id"], headers=h).json()["stock_qty"] == "5.000"


def test_postgres_dump_restore_recovers_sale_lines_tax_and_stock(pgclient, tmp_path):
    h, p = setup_stock(pgclient)
    sale = pgclient.post(
        "/api/sales", headers=h, json={"items": [{"product_id": p["id"], "quantity": "2"}]}
    ).json()
    source = pgclient.app.state.engine.url.database
    restored_name, restored_url = new_database()
    bindir = Path("C:/Program Files/PostgreSQL/17/bin")
    backup = tmp_path / "synthetic.dump"
    common = ["-h", "127.0.0.1", "-p", "55439", "-U", "datapyme_qa"]
    subprocess.run(
        [str(bindir / "pg_dump.exe"), *common, "-d", source, "-Fc", "-f", str(backup)],
        check=True,
        capture_output=True,
    )
    assert backup.stat().st_size > 0
    subprocess.run(
        [str(bindir / "pg_restore.exe"), *common, "-d", restored_name, "--exit-on-error", str(backup)],
        check=True,
        capture_output=True,
    )
    with TestClient(create_app(restored_url, testing=True)) as restored:
        result = restored.get("/api/sales/" + sale["id"], headers=h).json()
        assert result["total"] == "238.00" and result["vat_total"] == "38.00"
        assert result["tax_status"] == "responsible"
        assert result["items"][0]["quantity"] == "2.000"
        assert restored.get("/api/products/" + p["id"], headers=h).json()["stock_qty"] == "3.000"


def test_postgres_training_cleanup_and_activation_consents(pgclient):
    h = account(pgclient)
    p = pgclient.post(
        "/api/products",
        headers=h,
        json={
            "sku": "TRAIN",
            "name": "Práctica PG",
            "cost_price": "60",
            "sale_price": "100",
            "initial_stock": "5",
            "is_training_data": True,
        },
    ).json()
    assert (
        pgclient.post(
            "/api/sales",
            headers=h,
            json={"items": [{"product_id": p["id"], "quantity": "1"}], "is_training_data": True},
        ).status_code
        == 201
    )
    result = pgclient.post("/api/onboarding/complete-tour", headers=h, json={"action": "purge_training"})
    assert result.status_code == 200, result.text
    assert pgclient.get("/api/products", headers=h).json() == []


def test_postgres_historical_reference_and_void_do_not_change_stock(pgclient):
    h, p = setup_stock(pgclient)
    data = b"sale_number,occurred_at,sku,quantity,unit_price,unit_cost,vat_rate\nPG-HIST-1,2026-08-15,PG1,10,100,60,5\n"
    result = pgclient.post(
        "/api/imports/historical-sales?mode=commit",
        headers=h,
        files={"file": ("historical.csv", data, "text/csv")},
    )
    assert result.status_code == 201, result.text
    sale = pgclient.get("/api/sales", headers=h).json()[0]
    assert sale["external_reference"] == "PG-HIST-1" and sale["total"] == "1050.00"
    assert pgclient.get("/api/products/" + p["id"], headers=h).json()["stock_qty"] == "5.000"
    assert pgclient.post("/api/sales/" + sale["id"] + "/void", headers=h).status_code == 200
    assert pgclient.get("/api/products/" + p["id"], headers=h).json()["stock_qty"] == "5.000"
