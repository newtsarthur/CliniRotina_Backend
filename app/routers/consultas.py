from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies import get_current_user, garantir_acesso_idoso, resolver_id_idoso
from app.schemas.compromisso import (
    CompromissoCreate,
    CompromissoResponse,
    CompromissoUpdate,
    TipoCompromisso,
    agora_brasilia,
)
from app.services.compromisso import (
    create_compromisso,
    delete_compromisso,
    get_compromisso,
    list_compromissos,
    update_compromisso,
)
from app.services.vinculo import ids_idosos_acessiveis

router = APIRouter(prefix="/consultas", tags=["Consultas e Exames"])


def _carregar_com_acesso(compromisso_id: UUID, user: dict) -> dict:
    compromisso = get_compromisso(str(compromisso_id))
    if not compromisso:
        raise HTTPException(status_code=404, detail="Compromisso não encontrado")
    garantir_acesso_idoso(user, compromisso["id_idoso"])
    return compromisso


@router.post("", response_model=CompromissoResponse, status_code=201)
def criar_compromisso(body: CompromissoCreate, user: dict = Depends(get_current_user)):
    data = body.model_dump()
    data["id_idoso"] = resolver_id_idoso(user, str(body.id_idoso) if body.id_idoso else None)
    try:
        return create_compromisso(data)
    except FileExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=list[CompromissoResponse])
def listar_compromissos(
    id_idoso: UUID | None = Query(None),
    tipo: TipoCompromisso | None = Query(None),
    periodo: Literal["futuros", "passados", "todos"] = Query("futuros"),
    user: dict = Depends(get_current_user),
):
    if id_idoso:
        garantir_acesso_idoso(user, str(id_idoso))
        ids = [str(id_idoso)]
    else:
        ids = ids_idosos_acessiveis(user)

    agora = agora_brasilia().isoformat()
    return list_compromissos(
        ids,
        tipo=tipo,
        a_partir_de=agora if periodo == "futuros" else None,
        ate=agora if periodo == "passados" else None,
    )


@router.get("/{compromisso_id}", response_model=CompromissoResponse)
def consultar_compromisso(compromisso_id: UUID, user: dict = Depends(get_current_user)):
    return _carregar_com_acesso(compromisso_id, user)


@router.put("/{compromisso_id}", response_model=CompromissoResponse)
def atualizar_compromisso(
    compromisso_id: UUID,
    body: CompromissoUpdate,
    user: dict = Depends(get_current_user),
):
    data = body.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="Nenhum campo fornecido para atualização")
    atual = _carregar_com_acesso(compromisso_id, user)
    try:
        result = update_compromisso(str(compromisso_id), atual["id_idoso"], data)
    except FileExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail="Compromisso não encontrado")
    return result


@router.delete("/{compromisso_id}", status_code=204)
def excluir_compromisso(compromisso_id: UUID, user: dict = Depends(get_current_user)):
    _carregar_com_acesso(compromisso_id, user)
    if not delete_compromisso(str(compromisso_id)):
        raise HTTPException(status_code=404, detail="Compromisso não encontrado")
