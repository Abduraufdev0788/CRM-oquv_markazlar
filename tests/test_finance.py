"""
Finance API testlari — Payment va Expense.
"""
import pytest
from httpx import AsyncClient
from app.models.user import User


async def _get_token(client: AsyncClient) -> str:
    resp = await client.post("/api/v1/auth/login", data={
        "username": "+998901234567", "password": "testpass123"
    })
    return resp.json()["access_token"]


async def _create_student(client: AsyncClient, token: str, phone: str = "+998944556677") -> str:
    resp = await client.post("/api/v1/students/", json={
        "full_name": "To'lov testi", "phone": phone
    }, headers={"Authorization": f"Bearer {token}"})
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_create_payment(client: AsyncClient, admin_user: User):
    token = await _get_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    student_id = await _create_student(client, token)

    response = await client.post("/api/v1/finance/payments/", json={
        "student_id": student_id,
        "amount": 800000,
        "method": "cash",
        "period_month": 8,
        "period_year": 2024,
    }, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["amount"] == "800000.00"
    assert data["status"] == "confirmed"
    assert data["method"] == "cash"


@pytest.mark.asyncio
async def test_payment_updates_balance(client: AsyncClient, admin_user: User):
    """To'lov qilinganda o'quvchi balansi oshishi kerak."""
    token = await _get_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    student_id = await _create_student(client, token, "+998955667788")

    # Dastlabki balans 0
    student_before = (await client.get(f"/api/v1/students/{student_id}", headers=headers)).json()
    assert float(student_before["balance"]) == 0.0

    # To'lov
    await client.post("/api/v1/finance/payments/", json={
        "student_id": student_id,
        "amount": 500000,
        "method": "card",
        "period_month": 8,
        "period_year": 2024,
    }, headers=headers)

    # Balans oshishi kerak
    student_after = (await client.get(f"/api/v1/students/{student_id}", headers=headers)).json()
    assert float(student_after["balance"]) == 500000.0


@pytest.mark.asyncio
async def test_create_expense(client: AsyncClient, admin_user: User):
    token = await _get_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    from datetime import date
    response = await client.post("/api/v1/finance/expenses/", json={
        "category": "rent",
        "amount": 2000000,
        "description": "Avgust oyi ijarasi",
        "expense_date": str(date.today()),
    }, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["category"] == "rent"
    assert data["amount"] == "2000000.00"


@pytest.mark.asyncio
async def test_create_salary(client: AsyncClient, admin_user: User):
    token = await _get_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post("/api/v1/finance/salaries/", json={
        "user_id": str(admin_user.id),
        "period_month": 8,
        "period_year": 2024,
        "base_amount": 3000000,
        "bonus_amount": 200000,
        "penalty_amount": 0,
    }, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_create_salary_duplicate_rejected(client: AsyncClient, admin_user: User):
    """Bir xil oy uchun ikki marta maosh kiritilmasligi kerak."""
    token = await _get_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "user_id": str(admin_user.id),
        "period_month": 9,
        "period_year": 2024,
        "base_amount": 3000000,
    }
    await client.post("/api/v1/finance/salaries/", json=payload, headers=headers)
    response = await client.post("/api/v1/finance/salaries/", json=payload, headers=headers)
    assert response.status_code == 409
