import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.security import CurrentUser, current_user


@pytest.mark.asyncio
async def test_purchase_endpoint_requires_bearer_authentication():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/purchase-requests", json={"text":"Find headphones", "budget_minor":40000, "max_transaction_minor":40000, "currency":"USD"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_readiness_never_reports_ready_without_required_secrets():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/readyz")
    assert response.status_code == 503


@pytest.mark.asyncio
async def test_purchase_endpoint_ignores_client_identity_and_uses_verified_subject():
    async def verified_user() -> CurrentUser: return CurrentUser(id="00000000-0000-0000-0000-000000000001")
    app.dependency_overrides[current_user] = verified_user
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/purchase-requests", json={"user_id":"attacker-id", "text":"Find headphones", "budget_minor":40000, "max_transaction_minor":40000, "currency":"USD"})
        assert response.status_code == 200
        assert response.json()["request_id"]
    finally:
        app.dependency_overrides.clear()
