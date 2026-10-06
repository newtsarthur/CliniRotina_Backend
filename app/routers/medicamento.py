from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies import get_current_user, garantir_acesso_idoso, resolver_id_idoso
from app.schemas.medicamento import MedicamentoCreate, MedicamentoUpdate, MedicamentoResponse
from app.services.medicamento import (
    create_medicamento,
    list_medicamentos_de,
    get_medicamento,
    update_medicamento,
    delete_medicamento,
)
from app.services.vinculo import ids_idosos_acessiveis

router = APIRouter(prefix="/medicamentos", tags=["Medicamentos"])


def _carregar_com_acesso(medicamento_id: UUID, user: dict) -> dict:
    medicamento = get_medicamento(str(medicamento_id))
    if not medicamento:
        raise HTTPException(status_code=404, detail="Medicamento não encontrado")
    garantir_acesso_idoso(user, medicamento["id_idoso"])
    return medicamento


@router.post("", response_model=MedicamentoResponse, status_code=201)
def criar_medicamento(body: MedicamentoCreate, user: dict = Depends(get_current_user)):
    data = body.model_dump()
    data["id_idoso"] = resolver_id_idoso(user, str(body.id_idoso) if body.id_idoso else None)
    try:
        return create_medicamento(data)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=list[MedicamentoResponse])
def listar_medicamentos(
    id_idoso: UUID | None = Query(None),
    user: dict = Depends(get_current_user),
):
    if id_idoso:
        garantir_acesso_idoso(user, str(id_idoso))
        return list_medicamentos_de([str(id_idoso)])
    return list_medicamentos_de(ids_idosos_acessiveis(user))


@router.get("/{medicamento_id}", response_model=MedicamentoResponse)
def consultar_medicamento(medicamento_id: UUID, user: dict = Depends(get_current_user)):
    return _carregar_com_acesso(medicamento_id, user)


@router.put("/{medicamento_id}", response_model=MedicamentoResponse)
def atualizar_medicamento(
    medicamento_id: UUID,
    body: MedicamentoUpdate,
    user: dict = Depends(get_current_user),
):
    data = body.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="Nenhum campo fornecido para atualização")
    _carregar_com_acesso(medicamento_id, user)
    result = update_medicamento(str(medicamento_id), data)
    if not result:
        raise HTTPException(status_code=404, detail="Medicamento não encontrado")
    return result


@router.delete("/{medicamento_id}", status_code=204)
def excluir_medicamento(medicamento_id: UUID, user: dict = Depends(get_current_user)):
    _carregar_com_acesso(medicamento_id, user)
    if not delete_medicamento(str(medicamento_id)):
        raise HTTPException(status_code=404, detail="Medicamento não encontrado")
