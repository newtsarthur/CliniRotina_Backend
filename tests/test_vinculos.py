def test_idoso_nao_pode_criar_vinculo_403(client, usuarios):
    r = client.post(
        "/vinculos", json={"cpf_idoso": "22222222222"}, headers=usuarios["idoso"]["headers"]
    )
    assert r.status_code == 403


def test_vinculo_duplicado_409(client, usuarios):
    r = client.post(
        "/vinculos", json={"cpf_idoso": "11111111111"}, headers=usuarios["cuidador"]["headers"]
    )
    assert r.status_code == 409


def test_vinculo_com_cpf_de_cuidador_400(client, usuarios):
    r = client.post(
        "/vinculos", json={"cpf_idoso": "44444444444"}, headers=usuarios["cuidador"]["headers"]
    )
    assert r.status_code == 400


def test_vinculo_cpf_inexistente_404(client, usuarios):
    r = client.post(
        "/vinculos", json={"cpf_idoso": "99999999999"}, headers=usuarios["cuidador"]["headers"]
    )
    assert r.status_code == 404


def test_listagem_mostra_nomes_para_os_dois_lados(client, usuarios):
    lista = client.get("/vinculos", headers=usuarios["cuidador"]["headers"]).json()
    assert lista[0]["nome_idoso"] == "Maria Idosa"
    lista = client.get("/vinculos", headers=usuarios["idoso"]["headers"]).json()
    assert lista[0]["nome_cuidador"] == "Ana Cuidadora"


def test_terceiro_nao_remove_vinculo_403(client, usuarios):
    vinculo_id = client.get("/vinculos", headers=usuarios["cuidador"]["headers"]).json()[0]["id"]
    r = client.delete(f"/vinculos/{vinculo_id}", headers=usuarios["outro_idoso"]["headers"])
    assert r.status_code == 403
