import re

from pydantic import BaseModel, Field, field_validator


def normalizar_cpf(v: str) -> str:
    """Aceita CPF com ou sem máscara e armazena apenas os 11 dígitos."""
    digitos = re.sub(r"\D", "", v)
    if len(digitos) != 11:
        raise ValueError("CPF deve conter 11 dígitos")
    return digitos


class RegisterRequest(BaseModel):
    nome: str = Field(..., min_length=2, max_length=100)
    cpf: str = Field(..., min_length=11, max_length=14)
    telefone: str | None = Field(None, max_length=20)
    senha: str = Field(..., min_length=6)
    tipo_perfil: str = Field(..., min_length=1)

    _cpf = field_validator("cpf")(normalizar_cpf)

    @field_validator("tipo_perfil")
    @classmethod
    def perfil_valido(cls, v):
        valores = {"IDOSO", "CUIDADOR"}
        if v.upper() not in valores:
            raise ValueError(f"tipo_perfil deve ser um dos valores: {valores}")
        return v.upper()


class LoginRequest(BaseModel):
    cpf: str = Field(..., min_length=11, max_length=14)
    senha: str = Field(..., min_length=6)

    _cpf = field_validator("cpf")(normalizar_cpf)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    id: str
    nome: str
    cpf: str
    tipo_perfil: str


class UsuarioResponse(BaseModel):
    id: str
    nome: str
    cpf: str
    telefone: str | None = None
    tipo_perfil: str
