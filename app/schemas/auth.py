from pydantic import BaseModel, Field, validator


class RegisterRequest(BaseModel):
    nome: str = Field(..., min_length=2, max_length=100)
    cpf: str = Field(..., min_length=11, max_length=14)
    telefone: str | None = Field(None, max_length=20)
    senha: str = Field(..., min_length=6)
    tipo_perfil: str = Field(..., min_length=1)

    @validator("tipo_perfil")
    def perfil_valido(cls, v):
        valores = {"IDOSO", "CUIDADOR"}
        if v.upper() not in valores:
            raise ValueError(f"tipo_perfil deve ser um dos valores: {valores}")
        return v.upper()


class LoginRequest(BaseModel):
    cpf: str = Field(..., min_length=11, max_length=14)
    senha: str = Field(..., min_length=6)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    id: str
    nome: str
    cpf: str
    tipo_perfil: str