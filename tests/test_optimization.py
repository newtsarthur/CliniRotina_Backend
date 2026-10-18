"""Testes para o módulo de otimização (paralelismo CPU-bound + I/O-bound)."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from app.main import app
from app.services.optimization import (
    TimeSlot,
    compute_cost,
    run_optimization,
    _worker_hill_climb,
)
from app.schemas.optimization import OptimizationRequest, TimeSlotInput
from tests.fake_supabase import FakeSupabase


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def client(monkeypatch):
    """Cliente de teste com Supabase fake."""
    fake = FakeSupabase()
    for modulo in [
        "app.services.auth",
        "app.services.medicamento",
        "app.services.compromisso",
        "app.services.vinculo",
    ]:
        monkeypatch.setattr(f"{modulo}.get_supabase", lambda: fake)
    return TestClient(app)


@pytest.fixture
def usuarios(client):
    """Cria usuários de teste: idoso, cuidador vinculado, cuidador sem vínculo."""
    def registrar(nome, cpf, perfil):
        r = client.post(
            "/auth/register",
            json={"nome": nome, "cpf": cpf, "senha": "senha123", "tipo_perfil": perfil},
        )
        assert r.status_code == 201, r.text
        body = r.json()
        return {"id": body["id"], "headers": {"Authorization": f"Bearer {body['access_token']}"}}

    idoso = registrar("Maria Idosa", "11111111111", "IDOSO")
    cuidador = registrar("Ana Cuidadora", "22222222222", "CUIDADOR")
    cuidador_sem = registrar("Pedro Cuidador", "33333333333", "CUIDADOR")

    # Criar vínculo
    r = client.post(
        "/vinculos",
        json={"cpf_idoso": "11111111111", "parentesco": "Filha"},
        headers=cuidador["headers"],
    )
    assert r.status_code == 201, r.text

    return {
        "idoso": idoso,
        "cuidador": cuidador,
        "cuidador_sem_vinculo": cuidador_sem,
    }


# =============================================================================
# Testes unitários: função de custo
# =============================================================================

def test_compute_cost_no_conflicts():
    """Custo zero quando não há conflitos nem desvios."""
    slots = [
        TimeSlot(hora=8, minuto=0, fixo=False, id_ref="a"),
        TimeSlot(hora=12, minuto=0, fixo=False, id_ref="b"),
        TimeSlot(hora=18, minuto=0, fixo=False, id_ref="c"),
    ]
    cost, conflicts = compute_cost(slots, slots)
    assert cost == 0.0
    assert conflicts == 0


def test_compute_cost_exact_conflict():
    """Conflito exato (mesmo horário) penaliza pesado."""
    slots = [
        TimeSlot(hora=8, minuto=0, fixo=False, id_ref="a"),
        TimeSlot(hora=8, minuto=0, fixo=False, id_ref="b"),  # Mesmo horário
    ]
    cost, conflicts = compute_cost(slots, slots)
    assert cost >= 1000.0
    assert conflicts == 1


def test_compute_cost_near_conflict():
    """Quase conflito (< 15 min) penaliza moderado."""
    slots = [
        TimeSlot(hora=8, minuto=0, fixo=False, id_ref="a"),
        TimeSlot(hora=8, minuto=10, fixo=False, id_ref="b"),  # 10 min de diferença
    ]
    cost, conflicts = compute_cost(slots, slots)
    assert cost >= 100.0
    assert conflicts == 0  # Não é conflito exato


def test_compute_cost_fixed_times_preserved():
    """Horários fixos não são alterados na otimização (testa worker)."""
    # Estado inicial: fixo em 8:00, móvel em 8:05 (conflito)
    slots = [
        TimeSlot(hora=8, minuto=0, fixo=True, id_ref="fixo"),
        TimeSlot(hora=8, minuto=5, fixo=False, id_ref="movel"),
    ]
    original = slots[:]

    # Rodar worker com poucas iterações
    result = _worker_hill_climb(seed=42, slots_data=[(s.hora, s.minuto, s.fixo, s.id_ref) for s in slots],
                                 original_slots_data=[(s.hora, s.minuto, s.fixo, s.id_ref) for s in original],
                                 iterations=10)

    # Verificar que o fixo permaneceu em 8:00
    fixed_slot = next(s for s in result.slots if s.id_ref == "fixo")
    assert fixed_slot.hora == 8
    assert fixed_slot.minuto == 0
    assert fixed_slot.fixo is True


def test_compute_cost_deviation_penalty():
    """Desvio do horário original (não-fixos) adiciona custo."""
    original = [
        TimeSlot(hora=8, minuto=0, fixo=False, id_ref="a"),
    ]
    modified = [
        TimeSlot(hora=9, minuto=0, fixo=False, id_ref="a"),  # 60 min de desvio
    ]
    cost, _ = compute_cost(modified, original)
    assert cost == 60.0  # 1 ponto por minuto


# =============================================================================
# Testes unitários: otimização paralela vs sequencial
# =============================================================================

def test_run_optimization_sequential_vs_parallel_same_seed():
    """Com mesma seed/entrada, paralelo deve ter custo <= sequencial (melhor ou igual)."""
    slots = [
        TimeSlot(hora=7, minuto=0, fixo=False, id_ref="med_1"),
        TimeSlot(hora=7, minuto=10, fixo=False, id_ref="med_2"),
        TimeSlot(hora=7, minuto=20, fixo=False, id_ref="med_3"),
        TimeSlot(hora=9, minuto=30, fixo=True, id_ref="comp_1"),  # Fixo
        TimeSlot(hora=12, minuto=0, fixo=False, id_ref="med_4"),
        TimeSlot(hora=12, minuto=5, fixo=False, id_ref="med_5"),
    ]

    # Sequencial (1 worker)
    seq_result = run_optimization(slots, attempts=4, iterations=20, workers=1)

    # Paralelo (2+ workers)
    par_result = run_optimization(slots, attempts=4, iterations=20, workers=2)

    # Paralelo deve encontrar solução igual ou melhor (mais tentativas exploradas)
    assert par_result.cost_after <= seq_result.cost_after + 1e-9
    assert par_result.conflicts_after <= seq_result.conflicts_after

    # Modos corretos
    assert seq_result.mode == "sequencial"
    assert par_result.mode in ("paralelo", "sequencial (fallback: erro no pool)")


def test_run_optimization_fallback_sequential():
    """Se workers=1, deve rodar sequencial."""
    slots = [
        TimeSlot(hora=8, minuto=0, fixo=False, id_ref="a"),
        TimeSlot(hora=8, minuto=10, fixo=False, id_ref="b"),
    ]
    result = run_optimization(slots, attempts=2, iterations=5, workers=1)
    assert result.mode == "sequencial"
    assert result.workers_used == 1


def test_run_optimization_all_fixed_returns_early():
    """Se todos os slots são fixos, retorna sem otimizar."""
    slots = [
        TimeSlot(hora=8, minuto=0, fixo=True, id_ref="a"),
        TimeSlot(hora=12, minuto=0, fixo=True, id_ref="b"),
    ]
    result = run_optimization(slots, attempts=10, iterations=100, workers=4)
    assert result.mode == "sequencial (sem slots móveis)"
    assert result.cost_before == result.cost_after
    assert result.conflicts_before == result.conflicts_after


def test_run_optimization_deterministic_seeds():
    """Mesma entrada + mesmas seeds = mesmo resultado (reprodutibilidade)."""
    slots = [
        TimeSlot(hora=7, minuto=0, fixo=False, id_ref="a"),
        TimeSlot(hora=7, minuto=15, fixo=False, id_ref="b"),
        TimeSlot(hora=9, minuto=0, fixo=True, id_ref="fixo"),
    ]

    r1 = run_optimization(slots, attempts=4, iterations=10, workers=2)
    r2 = run_optimization(slots, attempts=4, iterations=10, workers=2)

    # Mesmo custo final (seeds determinísticas)
    assert r1.cost_after == r2.cost_after
    assert r1.conflicts_after == r2.conflicts_after


def test_worker_hill_climb_serializable():
    """Função worker deve ser serializável (nível de módulo)."""
    import pickle
    # Testar que a função pode ser pickled (necessário para ProcessPoolExecutor)
    pickled = pickle.dumps(_worker_hill_climb)
    unpickled = pickle.loads(pickled)

    slots_data = [(8, 0, False, "a"), (8, 10, False, "b")]
    result = unpickled(42, slots_data, slots_data, 5)
    assert isinstance(result.cost, float)
    assert isinstance(result.conflicts, int)


# =============================================================================
# Testes de schemas (validação Pydantic)
# =============================================================================

def test_optimization_request_valid():
    """Request válido passa na validação."""
    data = {
        "slots": [
            {"hora": 8, "minuto": 0, "fixo": False, "id_ref": "med_1"},
            {"hora": 9, "minuto": 0, "fixo": True, "id_ref": "comp_1"},
        ],
        "attempts": 8,
        "iterations": 50,
        "workers": 4,
    }
    req = OptimizationRequest(**data)
    assert len(req.slots) == 2
    assert req.attempts == 8


def test_optimization_request_duplicate_fixed_rejected():
    """Horários fixos duplicados são rejeitados."""
    data = {
        "slots": [
            {"hora": 8, "minuto": 0, "fixo": True, "id_ref": "a"},
            {"hora": 8, "minuto": 0, "fixo": True, "id_ref": "b"},  # Duplicata fixa
        ],
    }
    with pytest.raises(ValueError, match="Horários fixos não podem ter duplicatas"):
        OptimizationRequest(**data)


def test_optimization_request_all_fixed_rejected():
    """Todos fixos é rejeitado (nada a otimizar)."""
    data = {
        "slots": [
            {"hora": 8, "minuto": 0, "fixo": True, "id_ref": "a"},
            {"hora": 9, "minuto": 0, "fixo": True, "id_ref": "b"},
        ],
    }
    with pytest.raises(ValueError, match="Pelo menos um horário deve ser não-fixo"):
        OptimizationRequest(**data)


def test_optimization_request_limits():
    """Limites de tamanho e parâmetros são respeitados."""
    # Muitos slots
    data = {"slots": [{"hora": 8, "minuto": i, "fixo": False, "id_ref": f"x{i}"} for i in range(101)]}
    with pytest.raises(ValueError):
        OptimizationRequest(**data)

    # Attempts fora do range
    data = {"slots": [{"hora": 8, "minuto": 0, "fixo": False, "id_ref": "a"}], "attempts": 100}
    with pytest.raises(ValueError):
        OptimizationRequest(**data)


# =============================================================================
# Testes de integração: rota /optimization/suggest
# =============================================================================

def test_optimization_suggest_requires_auth(client):
    """Rota exige autenticação."""
    r = client.post("/optimization/suggest", json={"slots": []})
    assert r.status_code == 401


def test_optimization_suggest_idoso_own_data(client, usuarios):
    """Idoso pode otimizar seus próprios horários."""
    # Criar alguns medicamentos para o idoso
    headers = usuarios["idoso"]["headers"]
    for i in range(3):
        r = client.post("/medicamentos", json={
            "nome_remedio": f"Remedio{i}",
            "dosagem": "10mg",
            "hora": 8 + i,
            "minuto": 0,
        }, headers=headers)
        assert r.status_code == 201, r.text

    # Chamar otimização
    r = client.post("/optimization/suggest", json={
        "slots": [],  # Usar dados do banco
        "attempts": 4,
        "iterations": 10,
        "workers": 2,
    }, headers=headers)

    assert r.status_code == 200, r.text
    data = r.json()
    assert "original_slots" in data
    assert "optimized_slots" in data
    assert "cost_before" in data
    assert "cost_after" in data
    assert "conflicts_before" in data
    assert "conflicts_after" in data
    assert "execution_time_ms" in data
    assert "workers_used" in data
    assert "mode" in data
    assert data["cost_after"] <= data["cost_before"] + 1e-9


def test_optimization_suggest_cuidador_vinculado(client, usuarios):
    """Cuidador vinculado pode otimizar horários do idoso."""
    # Criar medicamentos para o idoso (pelo cuidador)
    headers = usuarios["cuidador"]["headers"]
    idoso_id = usuarios["idoso"]["id"]
    for i in range(2):
        r = client.post("/medicamentos", json={
            "id_idoso": idoso_id,
            "nome_remedio": f"Remedio{i}",
            "dosagem": "10mg",
            "hora": 8 + i,
            "minuto": 0,
        }, headers=headers)
        assert r.status_code == 201, r.text

    # Criar uma consulta (fixa) para o idoso
    r = client.post("/consultas", json={
        "id_idoso": idoso_id,
        "tipo": "CONSULTA",
        "especialidade": "Cardiologia",
        "data_hora": "2026-12-01T14:00:00",
    }, headers=headers)
    assert r.status_code == 201, r.text

    # Otimização
    r = client.post("/optimization/suggest", json={
        "attempts": 4,
        "iterations": 10,
    }, params={"id_idoso": idoso_id}, headers=headers)

    assert r.status_code == 200, r.text
    data = r.json()
    assert data["cost_after"] <= data["cost_before"] + 1e-9


def test_optimization_suggest_cuidador_sem_vinculo_403(client, usuarios):
    """Cuidador sem vínculo recebe 403."""
    headers = usuarios["cuidador_sem_vinculo"]["headers"]
    r = client.post("/optimization/suggest", json={
        "slots": [],
        "attempts": 2,
        "iterations": 5,
    }, params={"id_idoso": usuarios["idoso"]["id"]}, headers=headers)
    assert r.status_code == 403


def test_optimization_suggest_custom_slots(client, usuarios):
    """Slots customizados no body são usados (para testes/benchmark)."""
    headers = usuarios["idoso"]["headers"]
    r = client.post("/optimization/suggest", json={
        "slots": [
            {"hora": 7, "minuto": 0, "fixo": False, "id_ref": "test_1"},
            {"hora": 7, "minuto": 5, "fixo": False, "id_ref": "test_2"},
            {"hora": 9, "minuto": 30, "fixo": True, "id_ref": "fixo_1"},
        ],
        "attempts": 4,
        "iterations": 10,
        "workers": 2,
    }, headers=headers)

    assert r.status_code == 200, r.text
    data = r.json()
    # Deve ter 3 slots (2 móveis + 1 fixo)
    assert len(data["original_slots"]) == 3
    assert len(data["optimized_slots"]) == 3
    # Fixo deve ser preservado
    fixed = [s for s in data["optimized_slots"] if s["fixo"]]
    assert len(fixed) == 1
    assert fixed[0]["hora"] == 9
    assert fixed[0]["minuto"] == 30


# =============================================================================
# Testes de integração: rota /optimization/benchmark
# =============================================================================

def test_optimization_benchmark_requires_auth(client):
    r = client.post("/optimization/benchmark", json={"slots": []})
    assert r.status_code == 401


def test_optimization_benchmark_runs(client, usuarios):
    """Benchmark executa e retorna resultados comparativos."""
    headers = usuarios["idoso"]["headers"]
    # Criar dados
    for i in range(3):
        client.post("/medicamentos", json={
            "nome_remedio": f"R{i}", "dosagem": "10mg", "hora": 8 + i, "minuto": 0
        }, headers=headers)

    r = client.post("/optimization/benchmark", json={
        "slots": [],
        "attempts": 4,
        "iterations": 10,
        "workers_list": [1, 2],
        "repetitions": 2,
    }, headers=headers)

    assert r.status_code == 200, r.text
    data = r.json()
    assert "results" in data
    assert "best_config" in data
    assert "speedup_vs_sequential" in data
    assert len(data["results"]) == 2
    # Verificar estrutura
    for res in data["results"]:
        assert "workers" in res
        assert "mode" in res
        assert "execution_time_ms" in res
        assert "cost_after" in res


# =============================================================================
# Testes de regressão: garantir que rotas existentes não quebraram
# =============================================================================

def test_existing_routes_still_work(client, usuarios):
    """Teste de fumaça: rotas antigas continuam funcionando."""
    headers = usuarios["idoso"]["headers"]

    # Auth/me
    r = client.get("/auth/me", headers=headers)
    assert r.status_code == 200

    # Medicamentos CRUD
    r = client.post("/medicamentos", json={"nome_remedio": "Teste", "dosagem": "10mg", "hora": 8, "minuto": 0}, headers=headers)
    assert r.status_code == 201
    med_id = r.json()["id"]

    r = client.get("/medicamentos", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) == 1

    r = client.get(f"/medicamentos/{med_id}", headers=headers)
    assert r.status_code == 200

    r = client.put(f"/medicamentos/{med_id}", json={"dosagem": "20mg"}, headers=headers)
    assert r.status_code == 200

    r = client.delete(f"/medicamentos/{med_id}", headers=headers)
    assert r.status_code == 204

    # Consultas CRUD
    r = client.post("/consultas", json={
        "tipo": "CONSULTA", "especialidade": "Cardio", "data_hora": "2026-12-01T10:00:00"
    }, headers=headers)
    assert r.status_code == 201
    comp_id = r.json()["id"]

    r = client.get("/consultas", headers=headers)
    assert r.status_code == 200

    r = client.delete(f"/consultas/{comp_id}", headers=headers)
    assert r.status_code == 204

    # Vínculos
    r = client.get("/vinculos", headers=usuarios["cuidador"]["headers"])
    assert r.status_code == 200