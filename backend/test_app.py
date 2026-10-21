import pytest
import mongomock
from unittest.mock import patch

@pytest.fixture
def client():
    """Sets up an in-memory MongoDB instance and Flask test client."""
    mock_client = mongomock.MongoClient()
    mock_db = mock_client["movies_db"]
    mock_db.movies.insert_many([
        {"title": "The Dark Knight", "category": "thriller", "year": 2008},
        {"title": "Superbad", "category": "comedy", "year": 2007}
    ])

    with patch("app.db", mock_db):
        from app import app
        app.config["TESTING"] = True
        with app.test_client() as test_client:
            yield test_client

def test_get_movies_filtering_and_projection(client):
    """Verify endpoint status, filtering logic, and _id exclusion."""
    # Test category filtering
    res = client.get("/api/movies?category=thriller")
    assert res.status_code == 200
    
    data = res.get_json()
    assert data["count"] == 1
    assert data["movies"][0]["title"] == "The Dark Knight"
    assert "_id" not in data["movies"][0]

    # Test all movies fallback
    res_all = client.get("/api/movies")
    assert res_all.status_code == 200
    assert res_all.get_json()["count"] == 2

def test_health_endpoint(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.get_json() == {"status": "ok"}
