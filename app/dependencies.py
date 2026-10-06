from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.config import settings
from app.services.auth import get_user_by_id
from app.services.vinculo import cuidador_vinculado

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    """Valida o JWT do cabeçalho Authorization e devolve o usuário logado."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de acesso ausente",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = get_user_by_id(payload.get("sub", ""))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário do token não existe mais",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_perfil(*perfis: str):
    """Restringe a rota aos perfis informados; demais recebem 403."""

    def checker(user: dict = Depends(get_current_user)) -> dict:
        if user["tipo_perfil"] not in perfis:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acesso permitido apenas ao perfil: {', '.join(perfis)}",
            )
        return user

    return checker


def garantir_acesso_idoso(user: dict, id_idoso: str) -> None:
    """IDOSO acessa apenas os próprios dados; CUIDADOR, apenas idosos vinculados."""
    if user["tipo_perfil"] == "IDOSO" and user["id"] == id_idoso:
        return
    if user["tipo_perfil"] == "CUIDADOR" and cuidador_vinculado(user["id"], id_idoso):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Você não tem permissão para acessar os dados deste idoso",
    )


def resolver_id_idoso(user: dict, id_idoso: str | None) -> str:
    """Define o idoso alvo de uma criação: o próprio IDOSO ou o informado pelo CUIDADOR."""
    if id_idoso is None:
        if user["tipo_perfil"] == "IDOSO":
            return user["id"]
        raise HTTPException(
            status_code=422,
            detail="id_idoso é obrigatório para o perfil CUIDADOR",
        )
    garantir_acesso_idoso(user, id_idoso)
    return id_idoso
