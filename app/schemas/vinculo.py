from pydantic import BaseModel, Field, field_validator

from app.schemas.auth import normalizar_cpf


class VinculoCreate(BaseModel):
    cpf_idoso: str = Field(..., min_length=11, max_length=14)
    parentesco: str | None = Field(None, max_length=50)

    _cpf = field_validator("cpf_idoso")(normalizar_cpf)


class VinculoResponse(BaseModel):
    id: str
    id_cuidador: str
    id_idoso: str
    parentesco: str | None = None
    nome_idoso: str | None = None
    nome_cuidador: str | None = None
