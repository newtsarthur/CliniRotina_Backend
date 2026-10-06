from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_current_user, require_perfil
from app.schemas.vinculo import VinculoCreate, VinculoResponse
from app.services.vinculo import create_vinculo, delete_vinculo, get_vinculo, list_vinculos

router = APIRouter(prefix="/vinculos", tags=["Vínculos Cuidador-Idoso"])


@router.post("", response_model=VinculoResponse, status_code=201)
def criar_vinculo(body: VinculoCreate, user: dict = Depends(require_perfil("CUIDADOR"))):
    try:
        return create_vinculo(user["id"], body.cpf_idoso, body.parentesco)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=list[VinculoResponse])
def listar_vinculos(user: dict = Depends(get_current_user)):
    return list_vinculos(user)


@router.delete("/{vinculo_id}", status_code=204)
def excluir_vinculo(vinculo_id: UUID, user: dict = Depends(get_current_user)):
    vinculo = get_vinculo(str(vinculo_id))
    if not vinculo:
        raise HTTPException(status_code=404, detail="Vínculo não encontrado")
    if user["id"] not in (vinculo["id_cuidador"], vinculo["id_idoso"]):
        raise HTTPException(status_code=403, detail="Você não participa deste vínculo")
    delete_vinculo(str(vinculo_id))
