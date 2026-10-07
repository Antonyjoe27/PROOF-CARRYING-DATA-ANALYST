"""Tests for FastAPI endpoints."""
import pytest
from fastapi.testclient import TestClient

from backend.api.app import app

client = TestClient(app)


def test_api_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert "tables_loaded" in data


def test_load_demo_datasets_endpoint():
    res = client.post("/api/datasets/demo")
    assert res.status_code == 200
    data = res.json()
    assert "tables_loaded" in data
    assert len(data["tables_loaded"]) >= 2

    # Check datasets listing
    res2 = client.get("/api/datasets")
    assert res2.status_code == 200
    d2 = res2.json()
    assert d2["summary"]["total_files"] >= 2
    assert d2["summary"]["total_rows"] > 0


def test_rerun_proof_endpoint():
    # Load demo data first
    client.post("/api/datasets/demo")

    code = """
rev = sales_df.groupby("Product")["Revenue"].sum()
cost = costs_df.groupby("Product")["Cost"].sum()
profit = (rev - cost).sort_values(ascending=False)
result = {"result_type": "ranking", "metric": "profit", "selected_entity": str(profit.index[0]),
          "value": float(profit.iloc[0]), "unit": "INR", "direction": "highest",
          "values": {str(k): float(v) for k, v in profit.items()}}
print(json.dumps(result))
"""
    res = client.post(
        "/api/proof/rerun",
        json={
            "code": code,
            "question": "Which product generated the highest profit?",
            "original_value": 1240000.0,
            "original_entity": "Laptop Pro",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["matched"] is True
    assert data["status"] == "VERIFIED"
    assert "Laptop Pro" in str(data["rerun_result"])
