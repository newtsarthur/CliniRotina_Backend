import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.fake_supabase import FakeSupabase

MODULOS = [
    "app.services.auth",
    "app.services.medicamento",
    "app.services.compromisso",
    "app.services.vinculo",
]


@pytest.fixture
def client(monkeypatch):
    fake = FakeSupabase()
    for modulo in MODULOS:
        monkeypatch.setattr(f"{modulo}.get_supabase", lambda: fake)
    return TestClient(app)


def registrar(client, nome, cpf, perfil):
    r = client.post(
        "/auth/register",
        json={"nome": nome, "cpf": cpf, "senha": "senha123", "tipo_perfil": perfil},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    return {"id": body["id"], "headers": {"Authorization": f"Bearer {body['access_token']}"}}


@pytest.fixture
def usuarios(client):
    idoso = registrar(client, "Maria Idosa", "111.111.111-11", "IDOSO")
    outro_idoso = registrar(client, "João Idoso", "22222222222", "IDOSO")
    cuidador = registrar(client, "Ana Cuidadora", "33333333333", "CUIDADOR")
    cuidador_sem_vinculo = registrar(client, "Pedro Cuidador", "44444444444", "CUIDADOR")
    r = client.post(
        "/vinculos",
        json={"cpf_idoso": "11111111111", "parentesco": "Filha"},
        headers=cuidador["headers"],
    )
    assert r.status_code == 201, r.text
    return {
        "idoso": idoso,
        "outro_idoso": outro_idoso,
        "cuidador": cuidador,
        "cuidador_sem_vinculo": cuidador_sem_vinculo,
    }
