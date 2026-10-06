from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

# Horário de Brasília (sem horário de verão desde 2019). A coluna data_hora é
# TIMESTAMP sem fuso, então todo horário é armazenado como hora local de Brasília.
FUSO_BRASILIA = timezone(timedelta(hours=-3))

TipoCompromisso = Literal["CONSULTA", "EXAME"]


def agora_brasilia() -> datetime:
    return datetime.now(FUSO_BRASILIA).replace(tzinfo=None, microsecond=0)


def para_horario_local(v: datetime) -> datetime:
    if v.tzinfo is not None:
        v = v.astimezone(FUSO_BRASILIA).replace(tzinfo=None)
    return v.replace(second=0, microsecond=0)


def validar_data_futura(v: datetime | None) -> datetime | None:
    if v is None:
        return v
    v = para_horario_local(v)
    if v <= agora_brasilia():
        raise ValueError("A data e hora do compromisso não podem estar no passado")
    return v


def normalizar_tipo(v):
    return v.upper() if isinstance(v, str) else v


class CompromissoCreate(BaseModel):
    # Opcional para o IDOSO (assume o próprio id); obrigatório para o CUIDADOR.
    id_idoso: UUID | None = None
    tipo: TipoCompromisso
    especialidade: str = Field(..., min_length=2, max_length=100)
    local_atendimento: str | None = Field(None, max_length=255)
    data_hora: datetime
    preparo: str | None = None

    _tipo = field_validator("tipo", mode="before")(normalizar_tipo)
    _data = field_validator("data_hora")(validar_data_futura)


class CompromissoUpdate(BaseModel):
    tipo: TipoCompromisso | None = None
    especialidade: str | None = Field(None, min_length=2, max_length=100)
    local_atendimento: str | None = Field(None, max_length=255)
    data_hora: datetime | None = None
    preparo: str | None = None

    _tipo = field_validator("tipo", mode="before")(normalizar_tipo)
    _data = field_validator("data_hora")(validar_data_futura)


class CompromissoResponse(BaseModel):
    id: str
    id_idoso: str
    tipo: str
    especialidade: str
    local_atendimento: str | None = None
    data_hora: datetime
    preparo: str | None = None
