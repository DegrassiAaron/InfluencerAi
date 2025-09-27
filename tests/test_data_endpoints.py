from __future__ import annotations

from typing import Any, Dict

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai_influencer.webapp.main import app
from ai_influencer.webapp.storage import get_storage


@pytest.fixture(autouse=True)
def clear_storage():
    storage = get_storage()
    storage.clear()
    yield
    storage.clear()


def client() -> TestClient:
    return TestClient(app)


def create_sample(client: TestClient, payload: Dict[str, Any]) -> Dict[str, Any]:
    response = client.post("/api/data", json=payload)
    assert response.status_code == 201
    return response.json()


def test_list_initially_empty():
    response = client().get("/api/data")
    assert response.status_code == 200
    assert response.json() == {"items": []}


def test_create_and_retrieve_item():
    payload = {
        "name": "Briefing campagna",
        "category": "Campagna",
        "description": "Documentazione iniziale",
    }
    item = create_sample(client(), payload)

    assert item["id"] == 1
    assert item["name"] == payload["name"]
    assert item["category"] == payload["category"]
    assert item["description"] == payload["description"]
    assert "created_at" in item
    assert "updated_at" in item

    response = client().get(f"/api/data/{item['id']}")
    assert response.status_code == 200
    fetched = response.json()
    assert fetched == item


def test_list_returns_created_items():
    c = client()
    first = create_sample(
        c,
        {"name": "Studio target", "category": "Analisi", "description": "Persona"},
    )
    second = create_sample(
        c,
        {"name": "Script video", "category": "Contenuti", "description": "Storyboard"},
    )

    response = c.get("/api/data")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2
    assert data["items"][0]["id"] == first["id"]
    assert data["items"][1]["id"] == second["id"]


def test_update_item_and_clear_optional_fields():
    c = client()
    item = create_sample(
        c,
        {
            "name": "Report mensile",
            "category": "Report",
            "description": "Sintesi iniziale",
        },
    )

    response = c.put(
        f"/api/data/{item['id']}",
        json={"name": "Report mensile aggiornato", "category": "", "description": ""},
    )
    assert response.status_code == 200
    updated = response.json()
    assert updated["id"] == item["id"]
    assert updated["name"] == "Report mensile aggiornato"
    assert updated["category"] is None
    assert updated["description"] is None
    assert updated["updated_at"] != item["updated_at"]


def test_delete_item():
    c = client()
    item = create_sample(c, {"name": "Bozza post", "category": "", "description": ""})

    response = c.delete(f"/api/data/{item['id']}")
    assert response.status_code == 200
    assert response.json() == {"deleted": True}

    not_found = c.get(f"/api/data/{item['id']}")
    assert not_found.status_code == 404


def test_get_missing_item_returns_404():
    response = client().get("/api/data/999")
    assert response.status_code == 404


def test_update_missing_item_returns_404():
    response = client().put("/api/data/999", json={"name": "Inesistente"})
    assert response.status_code == 404


def test_delete_missing_item_returns_404():
    response = client().delete("/api/data/999")
    assert response.status_code == 404


def test_update_without_payload_returns_validation_error():
    response = client().put("/api/data/1", json={})
    assert response.status_code == 422


def test_create_requires_valid_name():
    response = client().post("/api/data", json={"name": "   "})
    assert response.status_code == 422
