import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root(client: AsyncClient):
    """Health check endpointni tekshirish."""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "running"


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_login_wrong_credentials(client: AsyncClient):
    """Noto'g'ri parol bilan login xatolik berishi kerak."""
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "+998901234567", "password": "wrongpassword"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, admin_user):
    """To'g'ri parol bilan login muvaffaqiyatli bo'lishi kerak."""
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "+998901234567", "password": "testpass123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_get_me(client: AsyncClient, admin_user):
    """Login qilib /me endpointni tekshirish."""
    # Login
    login_resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "+998901234567", "password": "testpass123"},
    )
    token = login_resp.json()["access_token"]

    # /me
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["phone"] == "+998901234567"
    assert data["role"] == "admin"
