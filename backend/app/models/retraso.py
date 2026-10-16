"""Esquemas de retrasos del alumnado."""

from datetime import date, datetime

from pydantic import BaseModel, Field


class RetrasoCreate(BaseModel):
    alumno_id: str = Field(min_length=1)
    fecha: date
    hora: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    modulo: str = Field(min_length=1)
    grupo: str | None = None


class Retraso(BaseModel):
    id: str
    alumno_id: str
    fecha: date
    hora: str
    modulo: str
    grupo: str | None = None
    curso_escolar: str
    registrado_por_id: str
    creado_en: datetime | None = None


class RetrasoPaginated(BaseModel):
    items: list[Retraso]
    page: int
    limit: int
    total: int
