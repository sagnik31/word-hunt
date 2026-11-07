import pytest
from fastapi.testclient import TestClient

from backend.api import app


@pytest.fixture(scope="module")
def client():
    # Entering the client runs the app lifespan, which builds the game engine.
    with TestClient(app) as c:
        yield c

def test_read_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {
        "message": "Word Hot-Cold Game API",
        "endpoints": ["/health", "/guess", "/similar_word", "/hint", "/quit", "/docs"],
    }

def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["target_word_loaded"] is True

def test_make_guess_invalid(client):
    response = client.post("/guess", json={"word": ""})
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False
    assert data["error"] == "Empty guess."

@pytest.mark.parametrize("path", ["/hint", "/similar_word"])
def test_help_endpoints_require_post(client, path):
    assert client.get(path).status_code == 405
    response = client.post(path)
    assert response.status_code == 200
    assert response.json()["rank"] >= 2

def test_make_guess_valid(client):
    # Assuming "dog" is in the vocabulary
    response = client.post("/guess", json={"word": "dog"})
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert "rank" in data

def test_plural_guess_reports_its_base_word(client):
    response = client.post("/guess", json={"word": "cats"})
    data = response.json()
    assert data["valid"] is True
    assert data["guess"] == "cats"
    assert data["matched"] == "cat"
