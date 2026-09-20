from pydantic import BaseModel, Field


class MedicamentoCreate(BaseModel):
    id_idoso: str = Field(..., min_length=1)
    nome_remedio: str = Field(..., min_length=1, max_length=100)
    dosagem: str = Field(..., min_length=1, max_length=50)
    instrucoes_uso: str | None = Field(None)


class MedicamentoUpdate(BaseModel):
    nome_remedio: str | None = Field(None, min_length=1, max_length=100)
    dosagem: str | None = Field(None, min_length=1, max_length=50)
    instrucoes_uso: str | None = Field(None)


class MedicamentoResponse(BaseModel):
    id: str
    id_idoso: str
    nome_remedio: str
    dosagem: str
    instrucoes_uso: str | None

    class Config:
        from_attributes = True