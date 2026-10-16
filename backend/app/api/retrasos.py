"""Endpoints de retrasos del alumnado."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response, status

from app.core.database import get_db
from app.core.deps import require_roles
from app.models.retraso import Retraso, RetrasoCreate, RetrasoPaginated
from app.models.usuario import UsuarioPublic
from app.services import auditoria_service, retraso_service

router = APIRouter(tags=["Retrasos"])


@router.post("/retrasos", response_model=Retraso, status_code=status.HTTP_201_CREATED)
async def create_retraso(
    payload: RetrasoCreate,
    response: Response,
    current: Annotated[UsuarioPublic, Depends(require_roles("docente", "admin"))],
) -> Retraso:
    """Registrar retraso; `registrado_por_id` sale del JWT."""
    db = get_db()
    retraso = await retraso_service.create_retraso(
        db, payload, registrado_por_id=current.id
    )
    response.headers["Location"] = f"/api/v1/retrasos/{retraso.id}"
    await auditoria_service.record(
        db,
        accion="retrasos.create",
        usuario_id=current.id,
        usuario_nombre=current.name,
        recurso_tipo="retraso",
        recurso_id=retraso.id,
        detalle={
            "alumno_id": retraso.alumno_id,
            "fecha": retraso.fecha.isoformat(),
            "hora": retraso.hora,
            "modulo": retraso.modulo,
        },
    )
    return retraso


@router.get("/retrasos/{id}", response_model=Retraso)
async def get_retraso(
    id: Annotated[str, Path()],
    _actor: Annotated[UsuarioPublic, Depends(require_roles("docente", "admin"))],
) -> Retraso:
    return await retraso_service.get_retraso(get_db(), id)


@router.get("/alumnos/{id}/retrasos", response_model=RetrasoPaginated)
async def list_alumno_retrasos(
    id: Annotated[str, Path(description="Identificador opaco del alumno")],
    current: Annotated[UsuarioPublic, Depends(require_roles("docente", "admin"))],
    curso_escolar: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> RetrasoPaginated:
    """Histórico individual (sin stats agregadas). Consulta auditada (datos de menores)."""
    db = get_db()
    result = await retraso_service.list_alumno_retrasos(
        db,
        id,
        curso_escolar=curso_escolar,
        page=page,
        limit=limit,
    )
    await auditoria_service.record(
        db,
        accion="retrasos.list_alumno",
        usuario_id=current.id,
        usuario_nombre=current.name,
        recurso_tipo="alumno",
        recurso_id=id,
        detalle={"curso_escolar": curso_escolar, "page": page, "limit": limit},
    )
    return result
