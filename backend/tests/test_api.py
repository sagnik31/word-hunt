from fastapi.testclient import TestClient

from backend.api import app

client = TestClient(app)

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {
        "message": "Word Hot-Cold Game API",
        "endpoints": ["/health", "/guess", "/hint", "/quit", "/docs"],
    }

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["ok", "degraded"]
    assert "target_word_loaded" in data

def test_make_guess_invalid():
    response = client.post("/guess", json={"word": ""})
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False
    assert data["error"] == "Empty guess."

def test_make_guess_valid():
    # Assuming "dog" is in the vocabulary
    response = client.post("/guess", json={"word": "dog"})
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert "rank" in data
