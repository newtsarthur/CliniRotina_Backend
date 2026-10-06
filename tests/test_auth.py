def test_login_aceita_cpf_com_ou_sem_mascara(client, usuarios):
    for cpf in ("11111111111", "111.111.111-11"):
        r = client.post("/auth/login", json={"cpf": cpf, "senha": "senha123"})
        assert r.status_code == 200
        assert r.json()["tipo_perfil"] == "IDOSO"


def test_login_senha_errada_retorna_401(client, usuarios):
    r = client.post("/auth/login", json={"cpf": "11111111111", "senha": "errada123"})
    assert r.status_code == 401


def test_cadastro_cpf_duplicado_retorna_409(client, usuarios):
    r = client.post(
        "/auth/register",
        json={"nome": "Dup", "cpf": "111.111.111-11", "senha": "senha123", "tipo_perfil": "IDOSO"},
    )
    assert r.status_code == 409


def test_cadastro_perfil_invalido_retorna_422(client):
    r = client.post(
        "/auth/register",
        json={"nome": "X", "cpf": "55555555555", "senha": "senha123", "tipo_perfil": "ADMIN"},
    )
    assert r.status_code == 422


def test_rota_protegida_sem_token_retorna_401(client):
    assert client.get("/medicamentos").status_code == 401
    assert client.get("/consultas").status_code == 401


def test_token_invalido_retorna_401(client):
    r = client.get("/auth/me", headers={"Authorization": "Bearer abc.def.ghi"})
    assert r.status_code == 401


def test_me_retorna_usuario_logado(client, usuarios):
    r = client.get("/auth/me", headers=usuarios["cuidador"]["headers"])
    assert r.status_code == 200
    assert r.json()["tipo_perfil"] == "CUIDADOR"
