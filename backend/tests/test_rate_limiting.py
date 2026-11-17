from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.security import auth_rate_limiter


def test_rate_limiting_trigger_429(monkeypatch):
    """Verify IP sliding window rate limiter protects auth endpoints with HTTP 429."""
    monkeypatch.setattr(settings, "auth_secret", "rate-limit-test-secret-123456789")
    auth_rate_limiter.reset()
    client = TestClient(app)

    # Trigger multiple requests up to limit
    responses = []
    for _ in range(15):
        resp = client.post("/api/auth/login", json={"email": "nonexistent@test.com", "password": "wrongpassword"})
        responses.append(resp.status_code)

    # 15 requests should either be 401 (invalid credentials)
    assert all(code == 401 for code in responses)

    # 16th request must be rate limited (429)
    resp_blocked = client.post("/api/auth/login", json={"email": "nonexistent@test.com", "password": "wrongpassword"})
    assert resp_blocked.status_code == 429
    assert "Too many authentication attempts" in resp_blocked.json()["detail"]
    assert "Retry-After" in resp_blocked.headers

    # Reset allows requests again
    auth_rate_limiter.reset()
    resp_resumed = client.post("/api/auth/login", json={"email": "nonexistent@test.com", "password": "wrongpassword"})
    assert resp_resumed.status_code == 401
