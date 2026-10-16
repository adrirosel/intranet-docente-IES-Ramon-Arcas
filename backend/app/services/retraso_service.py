"""Servicio de retrasos (alta + histórico individual; sin estadísticas)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from bson import ObjectId
from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from app.models.retraso import Retraso, RetrasoCreate, RetrasoPaginated
from app.models.usuario import utcnow

COLLECTION = "retrasos"


def curso_escolar_para_fecha(fecha: date) -> str:
    """
    Curso escolar español: 1 sep – 31 ago.
    Ej.: 2026-10-16 → 2026/2027; 2027-03-01 → 2026/2027.
    """
    if fecha.month >= 9:
        return f"{fecha.year}/{fecha.year + 1}"
    return f"{fecha.year - 1}/{fecha.year}"


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    await db[COLLECTION].create_index(
        [("alumno_id", 1), ("fecha", 1), ("hora", 1), ("modulo", 1)],
        unique=True,
        name="uniq_alumno_fecha_hora_modulo",
    )
    await db[COLLECTION].create_index([("alumno_id", 1), ("curso_escolar", 1), ("fecha", -1)])


def _oid(retraso_id: str) -> ObjectId:
    if not ObjectId.is_valid(retraso_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Retraso no encontrado")
    return ObjectId(retraso_id)


def _to_retraso(doc: dict[str, Any]) -> Retraso:
    fecha = doc["fecha"]
    if isinstance(fecha, datetime):
        fecha = fecha.date()
    return Retraso(
        id=str(doc["_id"]),
        alumno_id=doc["alumno_id"],
        fecha=fecha,
        hora=doc["hora"],
        modulo=doc["modulo"],
        grupo=doc.get("grupo"),
        curso_escolar=doc["curso_escolar"],
        registrado_por_id=doc["registrado_por_id"],
        creado_en=doc.get("creado_en"),
    )


async def create_retraso(
    db: AsyncIOMotorDatabase,
    payload: RetrasoCreate,
    *,
    registrado_por_id: str,
) -> Retraso:
    hoy = utcnow().date()
    if payload.fecha > hoy:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No se puede registrar un retraso con fecha futura",
        )

    curso = curso_escolar_para_fecha(payload.fecha)
    doc = {
        "alumno_id": payload.alumno_id,
        "fecha": datetime(payload.fecha.year, payload.fecha.month, payload.fecha.day),
        "hora": payload.hora,
        "modulo": payload.modulo,
        "grupo": payload.grupo,
        "curso_escolar": curso,
        "registrado_por_id": registrado_por_id,
        "creado_en": utcnow(),
    }
    try:
        result = await db[COLLECTION].insert_one(doc)
    except DuplicateKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un retraso para ese alumno, fecha, hora y módulo",
        ) from exc
    doc["_id"] = result.inserted_id
    return _to_retraso(doc)


async def get_retraso(db: AsyncIOMotorDatabase, retraso_id: str) -> Retraso:
    doc = await db[COLLECTION].find_one({"_id": _oid(retraso_id)})
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Retraso no encontrado")
    return _to_retraso(doc)


async def list_alumno_retrasos(
    db: AsyncIOMotorDatabase,
    alumno_id: str,
    *,
    curso_escolar: str | None = None,
    page: int = 1,
    limit: int = 10,
) -> RetrasoPaginated:
    query: dict[str, Any] = {"alumno_id": alumno_id}
    if curso_escolar:
        query["curso_escolar"] = curso_escolar

    total = await db[COLLECTION].count_documents(query)
    skip = (page - 1) * limit
    cursor = db[COLLECTION].find(query).sort("fecha", -1).skip(skip).limit(limit)
    items = [_to_retraso(doc) async for doc in cursor]
    return RetrasoPaginated(items=items, page=page, limit=limit, total=total)
