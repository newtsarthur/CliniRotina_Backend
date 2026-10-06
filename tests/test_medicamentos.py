MED = {"nome_remedio": "Losartana", "dosagem": "50mg"}


def test_idoso_cria_para_si_sem_informar_id(client, usuarios):
    r = client.post("/medicamentos", json=MED, headers=usuarios["idoso"]["headers"])
    assert r.status_code == 201
    assert r.json()["id_idoso"] == usuarios["idoso"]["id"]


def test_cuidador_vinculado_cria_para_idoso(client, usuarios):
    body = {**MED, "id_idoso": usuarios["idoso"]["id"]}
    r = client.post("/medicamentos", json=body, headers=usuarios["cuidador"]["headers"])
    assert r.status_code == 201


def test_cuidador_sem_vinculo_recebe_403(client, usuarios):
    body = {**MED, "id_idoso": usuarios["idoso"]["id"]}
    r = client.post("/medicamentos", json=body, headers=usuarios["cuidador_sem_vinculo"]["headers"])
    assert r.status_code == 403


def test_idoso_nao_acessa_medicamento_de_outro_idoso_403(client, usuarios):
    med = client.post("/medicamentos", json=MED, headers=usuarios["idoso"]["headers"]).json()
    outro = usuarios["outro_idoso"]["headers"]
    assert client.get(f"/medicamentos/{med['id']}", headers=outro).status_code == 403
    assert client.put(f"/medicamentos/{med['id']}", json={"dosagem": "1g"}, headers=outro).status_code == 403
    assert client.delete(f"/medicamentos/{med['id']}", headers=outro).status_code == 403
    assert client.get(f"/medicamentos?id_idoso={usuarios['idoso']['id']}", headers=outro).status_code == 403


def test_listagem_filtra_pelo_perfil(client, usuarios):
    client.post("/medicamentos", json=MED, headers=usuarios["idoso"]["headers"])
    client.post("/medicamentos", json=MED, headers=usuarios["outro_idoso"]["headers"])
    assert len(client.get("/medicamentos", headers=usuarios["idoso"]["headers"]).json()) == 1
    assert len(client.get("/medicamentos", headers=usuarios["cuidador"]["headers"]).json()) == 1
    assert client.get("/medicamentos", headers=usuarios["cuidador_sem_vinculo"]["headers"]).json() == []


def test_id_invalido_retorna_422_e_nao_500(client, usuarios):
    r = client.get("/medicamentos/nao-e-uuid", headers=usuarios["idoso"]["headers"])
    assert r.status_code == 422
