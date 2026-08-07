"""
Students API testlari.
"""
import pytest
from httpx import AsyncClient
from app.models.student import Student, StudentStatus
from app.core.security import hash_password
from app.models.user import User, UserRole


async def _get_token(client: AsyncClient, phone: str, password: str) -> str:
    resp = await client.post("/api/v1/auth/login", data={"username": phone, "password": password})
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_list_students_unauthorized(client: AsyncClient):
    """Token yo'q bo'lsa 403 qaytishi kerak."""
    response = await client.get("/api/v1/students/")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_and_get_student(client: AsyncClient, admin_user: User):
    token = await _get_token(client, "+998901234567", "testpass123")
    headers = {"Authorization": f"Bearer {token}"}

    # Yaratish
    response = await client.post("/api/v1/students/", json={
        "full_name": "Jasur Toshmatov",
        "phone": "+998911234567",
        "notes": "Test o'quvchi",
    }, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["full_name"] == "Jasur Toshmatov"
    assert data["status"] == "active"
    assert data["balance"] == "0.00"
    student_id = data["id"]

    # O'qish
    response = await client.get(f"/api/v1/students/{student_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["full_name"] == "Jasur Toshmatov"


@pytest.mark.asyncio
async def test_create_student_duplicate_phone(client: AsyncClient, admin_user: User):
    token = await _get_token(client, "+998901234567", "testpass123")
    headers = {"Authorization": f"Bearer {token}"}

    await client.post("/api/v1/students/", json={
        "full_name": "O'quvchi 1", "phone": "+998991112233"
    }, headers=headers)

    # Ikkinchi marta xuddi shu raqam bilan
    response = await client.post("/api/v1/students/", json={
        "full_name": "O'quvchi 2", "phone": "+998991112233"
    }, headers=headers)
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_update_student(client: AsyncClient, admin_user: User):
    token = await _get_token(client, "+998901234567", "testpass123")
    headers = {"Authorization": f"Bearer {token}"}

    create_resp = await client.post("/api/v1/students/", json={
        "full_name": "Eski Ism", "phone": "+998977001122"
    }, headers=headers)
    student_id = create_resp.json()["id"]

    update_resp = await client.put(f"/api/v1/students/{student_id}", json={
        "full_name": "Yangi Ism"
    }, headers=headers)
    assert update_resp.status_code == 200
    assert update_resp.json()["full_name"] == "Yangi Ism"


@pytest.mark.asyncio
async def test_delete_student_soft(client: AsyncClient, admin_user: User):
    """Soft delete — status EXPELLED ga o'tishi kerak."""
    token = await _get_token(client, "+998901234567", "testpass123")
    headers = {"Authorization": f"Bearer {token}"}

    create_resp = await client.post("/api/v1/students/", json={
        "full_name": "O'chiriluvchi", "phone": "+998933445566"
    }, headers=headers)
    student_id = create_resp.json()["id"]

    delete_resp = await client.delete(f"/api/v1/students/{student_id}", headers=headers)
    assert delete_resp.status_code == 200

    get_resp = await client.get(f"/api/v1/students/{student_id}", headers=headers)
    assert get_resp.json()["status"] == "expelled"


@pytest.mark.asyncio
async def test_list_students_pagination(client: AsyncClient, admin_user: User):
    token = await _get_token(client, "+998901234567", "testpass123")
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/api/v1/students/?skip=0&limit=5", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "total" in data
    assert "has_next" in data
