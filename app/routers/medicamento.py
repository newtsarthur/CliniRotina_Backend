from fastapi import APIRouter, HTTPException, Query
from uuid import UUID

from app.schemas.medicamento import MedicamentoCreate, MedicamentoUpdate, MedicamentoResponse
from app.services.medicamento import (
    create_medicamento,
    list_medicamentos,
    get_medicamento,
    update_medicamento,
    delete_medicamento,
)

router = APIRouter(prefix="/medicamentos", tags=["Medicamentos"])


@router.post("", response_model=MedicamentoResponse, status_code=201)
def criar_medicamento(body: MedicamentoCreate):
    try:
        return create_medicamento(body.model_dump())
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=list[MedicamentoResponse])
def listar_medicamentos(id_idoso: str | None = Query(None)):
    return list_medicamentos(id_idoso)


@router.get("/{medicamento_id}", response_model=MedicamentoResponse)
def consultar_medicamento(medicamento_id: str):
    result = get_medicamento(medicamento_id)
    if not result:
        raise HTTPException(status_code=404, detail="Medicamento não encontrado")
    return result


@router.put("/{medicamento_id}", response_model=MedicamentoResponse)
def atualizar_medicamento(medicamento_id: str, body: MedicamentoUpdate):
    data = {k: v for k, v in body.model_dump(exclude_unset=True).items()}
    if not data:
        raise HTTPException(status_code=400, detail="Nenhum campo fornecido para atualização")
    result = update_medicamento(medicamento_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="Medicamento não encontrado")
    return result


@router.delete("/{medicamento_id}", status_code=204)
def excluir_medicamento(medicamento_id: str):
    ok = delete_medicamento(medicamento_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Medicamento não encontrado")