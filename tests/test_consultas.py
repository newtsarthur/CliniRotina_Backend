from datetime import timedelta

from app.schemas.compromisso import agora_brasilia


def futuro(dias=7):
    return (agora_brasilia() + timedelta(days=dias)).replace(hour=9, minute=30).isoformat()


def consulta(**extra):
    return {"tipo": "CONSULTA", "especialidade": "Cardiologia", "local_atendimento": "UBS Centro",
            "data_hora": futuro(), **extra}


def test_idoso_agenda_consulta(client, usuarios):
    r = client.post("/consultas", json=consulta(), headers=usuarios["idoso"]["headers"])
    assert r.status_code == 201, r.text
    assert r.json()["id_idoso"] == usuarios["idoso"]["id"]


def test_tipo_em_minusculas_e_normalizado(client, usuarios):
    r = client.post("/consultas", json=consulta(tipo="exame"), headers=usuarios["idoso"]["headers"])
    assert r.status_code == 201
    assert r.json()["tipo"] == "EXAME"


def test_tipo_invalido_422(client, usuarios):
    r = client.post("/consultas", json=consulta(tipo="CIRURGIA"), headers=usuarios["idoso"]["headers"])
    assert r.status_code == 422


def test_data_no_passado_422(client, usuarios):
    passado = (agora_brasilia() - timedelta(days=1)).isoformat()
    r = client.post("/consultas", json=consulta(data_hora=passado), headers=usuarios["idoso"]["headers"])
    assert r.status_code == 422
    assert "passado" in r.text


def test_conflito_de_horario_409(client, usuarios):
    h = usuarios["idoso"]["headers"]
    assert client.post("/consultas", json=consulta(), headers=h).status_code == 201
    r = client.post("/consultas", json=consulta(especialidade="Ortopedia"), headers=h)
    assert r.status_code == 409


def test_cuidador_obrigado_a_informar_idoso_422(client, usuarios):
    r = client.post("/consultas", json=consulta(), headers=usuarios["cuidador"]["headers"])
    assert r.status_code == 422


def test_cuidador_sem_vinculo_403(client, usuarios):
    body = consulta(id_idoso=usuarios["idoso"]["id"])
    r = client.post("/consultas", json=body, headers=usuarios["cuidador_sem_vinculo"]["headers"])
    assert r.status_code == 403


def test_cuidador_vinculado_ve_e_remarca(client, usuarios):
    c = client.post("/consultas", json=consulta(), headers=usuarios["idoso"]["headers"]).json()
    h = usuarios["cuidador"]["headers"]
    lista = client.get("/consultas", headers=h).json()
    assert [x["id"] for x in lista] == [c["id"]]
    r = client.put(f"/consultas/{c['id']}", json={"data_hora": futuro(10)}, headers=h)
    assert r.status_code == 200


def test_outro_idoso_403_em_todas_operacoes(client, usuarios):
    c = client.post("/consultas", json=consulta(), headers=usuarios["idoso"]["headers"]).json()
    h = usuarios["outro_idoso"]["headers"]
    assert client.get(f"/consultas/{c['id']}", headers=h).status_code == 403
    assert client.put(f"/consultas/{c['id']}", json={"preparo": "x"}, headers=h).status_code == 403
    assert client.delete(f"/consultas/{c['id']}", headers=h).status_code == 403


def test_listagem_ordenada_e_filtrada_por_tipo(client, usuarios):
    h = usuarios["idoso"]["headers"]
    client.post("/consultas", json=consulta(data_hora=futuro(20)), headers=h)
    client.post("/consultas", json=consulta(tipo="EXAME", especialidade="Hemograma", data_hora=futuro(3)), headers=h)
    todos = client.get("/consultas", headers=h).json()
    assert [x["tipo"] for x in todos] == ["EXAME", "CONSULTA"]
    exames = client.get("/consultas?tipo=EXAME", headers=h).json()
    assert len(exames) == 1


def test_excluir_e_depois_404(client, usuarios):
    h = usuarios["idoso"]["headers"]
    c = client.post("/consultas", json=consulta(), headers=h).json()
    assert client.delete(f"/consultas/{c['id']}", headers=h).status_code == 204
    assert client.get(f"/consultas/{c['id']}", headers=h).status_code == 404
