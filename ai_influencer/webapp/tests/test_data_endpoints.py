from __future__ import annotations

from fastapi.testclient import TestClient

from ai_influencer.webapp.main import app
from ai_influencer.webapp.storage import delete_data, get_storage, list_data

client = TestClient(app)


def setup_module(module: object) -> None:
    storage = get_storage()
    for item in list_data(storage):
        delete_data(storage, item["id"])


def test_data_crud_flow() -> None:
    create_response = client.post("/api/data", json={"name": "Elemento"})
    assert create_response.status_code == 201
    created = create_response.json()
    assert "id" in created
    data_id = created["id"]
    assert created["name"] == "Elemento"

    list_response = client.get("/api/data")
    assert list_response.status_code == 200
    items = list_response.json()["items"]
    assert any(item["id"] == data_id for item in items)

    get_response = client.get(f"/api/data/{data_id}")
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "Elemento"

    update_response = client.put(f"/api/data/{data_id}", json={"name": "Aggiornato"})
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Aggiornato"

    delete_response = client.delete(f"/api/data/{data_id}")
    assert delete_response.status_code == 200
    assert delete_response.json() == {"deleted": True}

    missing_response = client.get(f"/api/data/{data_id}")
    assert missing_response.status_code == 404


def test_create_requires_payload() -> None:
    response = client.post("/api/data", json={})
    assert response.status_code == 400


def test_missing_item_responses() -> None:
    assert client.get("/api/data/9999").status_code == 404
    assert (
        client.put("/api/data/9999", json={"name": "test"}).status_code == 404
    )
    assert client.delete("/api/data/9999").status_code == 404
