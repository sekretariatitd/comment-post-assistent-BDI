from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import UserRole
from app.services import auth_service


async def _make_user(db: AsyncSession, active: bool = True) -> None:
    user = await auth_service.create_user(db, "Reviewer@Example.com", "pw-123", UserRole.reviewer)
    user.is_active = active
    await db.flush()


async def test_login_and_me(client: AsyncClient, db_session: AsyncSession) -> None:
    await _make_user(db_session)

    resp = await client.post(
        "/api/v1/auth/login", json={"email": "reviewer@example.com", "password": "pw-123"}
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    body = me.json()
    assert body["email"] == "reviewer@example.com"
    assert body["role"] == "reviewer"
    assert "password_hash" not in body


async def test_login_wrong_password(client: AsyncClient, db_session: AsyncSession) -> None:
    await _make_user(db_session)
    resp = await client.post(
        "/api/v1/auth/login", json={"email": "reviewer@example.com", "password": "nope"}
    )
    assert resp.status_code == 401


async def test_login_unknown_email(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/auth/login", json={"email": "ghost@example.com", "password": "pw-123"}
    )
    assert resp.status_code == 401


async def test_login_inactive_user(client: AsyncClient, db_session: AsyncSession) -> None:
    await _make_user(db_session, active=False)
    resp = await client.post(
        "/api/v1/auth/login", json={"email": "reviewer@example.com", "password": "pw-123"}
    )
    assert resp.status_code == 401


async def test_me_requires_token(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/auth/me")).status_code == 401
    bad = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer garbage"})
    assert bad.status_code == 401
