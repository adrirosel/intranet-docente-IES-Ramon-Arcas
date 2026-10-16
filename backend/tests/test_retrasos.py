"""Tests del módulo de retrasos (requieren Mongo + Redis)."""

import os
from collections.abc import AsyncIterator
from datetime import date, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017")
os.environ.setdefault("MONGODB_DB", "intranet_docente_test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")
os.environ.setdefault("JWT_SECRET", "test-secret-at-least-32-characters!!")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-client-id")
os.environ.setdefault("COOKIE_SECURE", "false")
os.environ.setdefault("ENVIRONMENT", "development")

from app.core.config import get_settings

get_settings.cache_clear()

from app.core.database import get_db, get_redis
from app.main import app
from app.models.usuario import Role, UsuarioEstado, UsuarioPatch
from app.services import auth_service, usuario_service


def _google_claims(**overrides: object) -> dict:
    base = {
        "email": "docente@example.com",
        "sub": "google-sub-1",
        "name": "Docente Demo",
        "email_verified": True,
    }
    base.update(overrides)
    return base


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            db = get_db()
            await db["usuarios"].delete_many({})
            await db["retrasos"].delete_many({})
            await db["auditoria"].delete_many({})
            redis = get_redis()
            async for key in redis.scan_iter("refresh:*"):
                await redis.delete(key)
            yield ac


async def _activate_as(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    *,
    email: str,
    sub: str,
    name: str,
    roles: list[Role],
) -> str:
    monkeypatch.setattr(
        auth_service,
        "verify_google_id_token",
        lambda _t: _google_claims(email=email, sub=sub, name=name),
    )
    login = await client.post("/api/v1/auth/google", json={"id_token": f"fake-{sub}"})
    access = login.json()["access_token"]
    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access}"})
    await usuario_service.patch_usuario(
        get_db(),
        me.json()["id"],
        UsuarioPatch(roles=roles, estado=UsuarioEstado.activo),
    )
    login2 = await client.post("/api/v1/auth/google", json={"id_token": f"fake-{sub}"})
    return login2.json()["access_token"]


@pytest.mark.asyncio
async def test_retrasos_forbidden_without_role(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    access = await _activate_as(
        client,
        monkeypatch,
        email="tutor@example.com",
        sub="google-tutor-r",
        name="Tutor",
        roles=[Role.tutor],
    )
    hoy = date.today().isoformat()
    res = await client.post(
        "/api/v1/retrasos",
        headers={"Authorization": f"Bearer {access}"},
        json={"alumno_id": "alu-1", "fecha": hoy, "hora": "08:20", "modulo": "DWES"},
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_retrasos_create_get_historico_and_duplicate(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    access = await _activate_as(
        client,
        monkeypatch,
        email="doc-r@example.com",
        sub="google-doc-r",
        name="Docente R",
        roles=[Role.docente],
    )
    headers = {"Authorization": f"Bearer {access}"}
    hoy = date.today().isoformat()

    created = await client.post(
        "/api/v1/retrasos",
        headers=headers,
        json={
            "alumno_id": "alu-42",
            "fecha": hoy,
            "hora": "08:20",
            "modulo": "DWES",
            "grupo": "2DAW",
        },
    )
    assert created.status_code == 201
    assert created.headers.get("location", "").startswith("/api/v1/retrasos/")
    body = created.json()
    assert body["alumno_id"] == "alu-42"
    assert body["registrado_por_id"]
    assert "/" in body["curso_escolar"]
    retraso_id = body["id"]

    detalle = await client.get(f"/api/v1/retrasos/{retraso_id}", headers=headers)
    assert detalle.status_code == 200
    assert detalle.json()["id"] == retraso_id

    hist = await client.get(
        "/api/v1/alumnos/alu-42/retrasos?page=1&limit=10",
        headers=headers,
    )
    assert hist.status_code == 200
    hist_body = hist.json()
    assert hist_body["total"] >= 1
    assert any(i["id"] == retraso_id for i in hist_body["items"])

    dup = await client.post(
        "/api/v1/retrasos",
        headers=headers,
        json={"alumno_id": "alu-42", "fecha": hoy, "hora": "08:20", "modulo": "DWES"},
    )
    assert dup.status_code == 409


@pytest.mark.asyncio
async def test_retrasos_future_date_422(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    access = await _activate_as(
        client,
        monkeypatch,
        email="doc-fut@example.com",
        sub="google-doc-fut",
        name="Docente Fut",
        roles=[Role.docente],
    )
    futuro = (date.today() + timedelta(days=2)).isoformat()
    res = await client.post(
        "/api/v1/retrasos",
        headers={"Authorization": f"Bearer {access}"},
        json={"alumno_id": "alu-9", "fecha": futuro, "hora": "09:00", "modulo": "DIW"},
    )
    assert res.status_code == 422
