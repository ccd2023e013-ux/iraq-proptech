from fastapi.testclient import TestClient


def test_liveness(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["environment"] == "test"


def test_request_id_is_generated_and_echoed(client: TestClient) -> None:
    generated = client.get("/api/v1/health").headers["X-Request-ID"]
    assert len(generated) == 32

    echoed = client.get("/api/v1/health", headers={"X-Request-ID": "abc-123"})
    assert echoed.headers["X-Request-ID"] == "abc-123"


def test_malicious_request_id_is_replaced(client: TestClient) -> None:
    response = client.get("/api/v1/health", headers={"X-Request-ID": "bad\nid<script>"})
    assert response.headers["X-Request-ID"] != "bad\nid<script>"


def test_security_headers(client: TestClient) -> None:
    headers = client.get("/api/v1/health").headers
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
    # HSTS only in production (behind TLS)
    assert "Strict-Transport-Security" not in headers


def test_not_found_uses_error_envelope(client: TestClient) -> None:
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "NOT_FOUND"
    assert error["request_id"] == response.headers["X-Request-ID"]


def test_openapi_is_published(client: TestClient) -> None:
    response = client.get("/api/v1/openapi.json")
    assert response.status_code == 200
    assert "/api/v1/health" in response.json()["paths"]
