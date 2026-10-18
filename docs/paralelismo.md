# Documentação: Paralelismo no Módulo de Otimização (CliniRotina)

> **Disciplina:** Programação Concorrente e Paralela  
> **Projeto:** CliniRotina Backend — Sprint 05  
> **Data:** 2026-10-10

---

## 1. Resumo

Este documento descreve a implementação de paralelismo no módulo de otimização de horários do CliniRotina. O módulo resolve o problema de reorganizar lembretes de medicamentos (móveis) ao redor de consultas e exames (fixos) para minimizar conflitos de horário, usando **hill climbing** com múltiplas tentativas independentes executadas em **processos paralelos** (CPU-bound) e buscas de banco de dados em **threads** (I/O-bound).

---

## 2. O que foi paralelizado

| Tipo | Onde | Tecnologia | Por que |
|------|------|------------|---------|
| **I/O-bound** | Rota `POST /optimization/suggest` | `ThreadPoolExecutor` (3 workers) + `asyncio.gather` | Busca simultânea de medicamentos, consultas e exames no Supabase (3 queries SELECT independentes) |
| **CPU-bound** | `app/services/optimization.py` → `run_optimization()` | `ProcessPoolExecutor` (N workers, padrão = `cpu_count()`) | Executa múltiplas tentativas de hill climbing em processos separados, contornando o GIL do Python |

---

## 3. Processos vs Threads: quando usar cada um

### Threads (I/O-bound)
- **Uso:** Operações que esperam por rede/disco (queries no Supabase, HTTP requests, leitura de arquivos)
- **Por que threads:** O GIL é liberado durante I/O → múltiplas threads podem progredir simultaneamente
- **Implementação:** `ThreadPoolExecutor(max_workers=3)` + `loop.run_in_executor()` para não bloquear o event loop do FastAPI

### Processos (CPU-bound)
- **Uso:** Cálculo puro (hill climbing: geração de vizinhos, cálculo de custo, comparação, iterações)
- **Por que processos:** Cada processo tem seu **próprio GIL** → verdadeiro paralelismo em múltiplos núcleos
- **Serialização:** Dados simples (`dataclass` frozen, tipos primitivos) → pickling rápido via `multiprocessing`
- **Fallback automático:** Se `ProcessPoolExecutor` falhar (ex.: ambiente serverless com 1 vCPU), cai para execução sequencial

---

## 4. O GIL (Global Interpreter Lock) e por que processos

O **GIL** do CPython permite que apenas uma thread execute bytecode Python por vez. Isso significa:
- **Threads NÃO aceleram** código CPU-bound puro (o GIL serializa a execução)
- **Processos SÃO necessários** para paralelismo real em CPU-bound — cada processo tem seu próprio interpretador e GIL

> **No nosso caso:** O hill climbing faz milhões de operações aritméticas e de comparação por segundo. Com threads, o GIL faria as 8 tentativas rodarem praticamente em sequência. Com `ProcessPoolExecutor`, cada tentativa roda em um núcleo físico distinto.

---

## 5. Arquitetura do código

```
POST /optimization/suggest
        │
        ▼
┌───────────────────────┐
│  I/O PARALELO (threads)│
│  ThreadPoolExecutor(3) │
│  ├─ list_medicamentos  │
│  ├─ list_consultas     │
│  └─ list_exames        │
└───────────┬───────────┘
            │ (dados combinados → lista de TimeSlot)
            ▼
┌──────────────────────────┐
│  CPU PARALELO (processos) │
│  ProcessPoolExecutor(N)   │
│  ├─ attempt 1 (seed=42)   │
│  ├─ attempt 2 (seed=1042) │
│  ├─ ...                   │
│  └─ attempt N             │
└───────────┬──────────────┘
            │ (melhor resultado)
            ▼
    Retorna OptimizationResponse
```

---

## 6. Como rodar o benchmark

```bash
cd /home/batmantw/Downloads/"Projeto da facul"/CliniRotina_Backend
source .venv/bin/activate

# Benchmark padrão (3 repetições, workers 1/2/4)
python scripts/benchmark_paralelismo.py

# Personalizado
python scripts/benchmark_paralelismo.py \
  --attempts 8 \
  --iterations 50 \
  --workers 4 \
  --repetitions 5
```

### Parâmetros

| Parâmetro | Padrão | Descrição |
|-----------|--------|-----------|
| `--attempts` | 8 | Tentativas independentes (seeds diferentes) |
| `--iterations` | 50 | Iterações de hill climbing por tentativa |
| `--workers` | auto (cpu_count) | Workers paralelos a testar |
| `--repetitions` | 3 | Repetições por configuração para média |

---

## 7. Interpretando os resultados

Exemplo de saída (ambiente com 4 CPUs):

```
====================================================================================================
RESULTADOS DO BENCHMARK
====================================================================================================
 Workers |         Modo | Tempo Médio (ms) |  Desvio (ms) |  Custo Médio |  Conflitos |  Speedup
------------------------------------------------------------------------------------------------
       1 |   sequencial |           375.21 |         7.44 |        20.00 |        0.0 |    1.00x
       2 |     paralelo |           225.44 |        40.64 |        20.00 |        0.0 |    1.66x
       4 |     paralelo |           139.00 |        16.42 |        20.00 |        0.0 |    2.70x
------------------------------------------------------------------------------------------------

✅ Melhor configuração: 4 worker(s) (paralelo) - 139.0ms médio
   Speedup vs sequencial: 2.70x
   Custo final: 20.0 | Conflitos: 0.0
```

### O que observar

1. **Speedup** = `tempo_sequencial / tempo_paralelo`
   - Ideal = N workers (speedup linear)
   - Real < N devido a: overhead de criação de processos, pickling de dados, sincronização, cache misses

2. **Qualidade da solução (custo/conflitos)**
   - O custo médio deve ser **igual ou menor** no paralelo vs sequencial
   - Se o paralelo der custo *pior*, pode ser azar estatístico (hill climbing é estocástico) → aumente `--repetitions`

3. **Desvio padrão**
   - Alto desvio = instabilidade (ex.: GC, outros processos no sistema)
   - Baixo desvio = resultados consistentes

4. **Modo "sequencial (fallback)"**
   - Aparece se `ProcessPoolExecutor` lançar exceção (comum em serverless/Vercel)
   - O código **não quebra**, apenas degrada graciosamente para 1 worker

---

## 8. Testes automatizados

```bash
# Rodar toda a suíte (52 testes: 30 antigos + 22 novos de otimização)
pytest -v

# Apenas testes de otimização
pytest tests/test_optimization.py -v
```

### Cobertura dos testes novos (`test_optimization.py`)

| Teste | O que valida |
|-------|--------------|
| `test_compute_cost_*` | Função de custo: conflitos, janela noturna, espaçamento, horários fixos |
| `test_worker_hill_climb_*` | Worker individual: determinismo por seed, respeita fixos, melhora custo |
| `test_run_optimization_*` | Orquestrador: modo sequencial/paralelo, fallback, workers=1, reproducibilidade |
| `test_optimization_suggest_*` | Rota HTTP: IDOSO próprio, CUIDADOR vinculado, 403 sem vínculo, slots customizados |
| `test_optimization_benchmark_*` | Rota de benchmark: sequencial vs paralelo, estrutura da resposta |

---

## 9. Testar via Swagger (manual)

```bash
# Subir servidor
uvicorn app.main:app --reload --port 8000
```

Abrir: http://localhost:8000/docs

### Fluxo de teste

1. **POST `/auth/register`** → criar IDOSO + CUIDADOR
2. **POST `/vinculos`** (como cuidador) → vincular ao idoso
3. **POST `/medicamentos`** (como cuidador, `id_idoso=...`) → criar 3-5 medicamentos com horários próximos (ex.: 07:00, 07:10, 07:25)
4. **POST `/consultas`** (como cuidador) → criar 1-2 consultas fixas
5. **POST `/optimization/suggest`** (como cuidador, `id_idoso=...`) → ver sugestão otimizada
   - Observar: `cost_after < cost_before`, `conflicts_after = 0`, `mode = "paralelo"`, `workers_used = N`
6. **POST `/optimization/benchmark`** → ver tabela comparativa

---

## 10. Decisões de design e trade-offs

| Decisão | Justificativa |
|---------|---------------|
| `dataclass(frozen=True)` para `TimeSlot` | Imutável → seguro para multiprocessing, hashável, serializável |
| Seeds determinísticas (`42 + i*1000`) | Reprodutibilidade: mesmo input → mesmo output (facilita testes e debug) |
| Fallback sequencial automático | Robustez em serverless (Vercel, AWS Lambda) onde `cpu_count=1` ou `fork` bloqueado |
| `slots` opcional no request | Permite testar/benchmarkar com dados sintéticos sem depender do banco |
| Limite `max_length=100` nos slots | Proteção contra DoS (input muito grande) |
| Validação: horários fixos sem duplicatas | Conflito irreconciliável detectado cedo (422) |
| Validação: pelo menos 1 móvel | Otimização sem graus de liberdade não faz sentido |

---

## 11. Limitações conhecidas

1. **Overhead de processos:** Para poucas tentativas/iterações, o overhead pode superar o ganho. Use `attempts >= 4` e `iterations >= 20`.
2. **Memória:** Cada processo copia os dados de entrada (pickling). Para `slots > 500`, considere `shared_memory` ou reduzir workers.
3. **Estocasticidade:** Hill climbing pode convergir para ótimos locais. Múltiplas tentativas (`attempts`) mitigam isso.
4. **Serverless:** Em Vercel/AWS Lambda, `ProcessPoolExecutor` pode falhar → fallback sequencial automático (já implementado).

---

## 12. Referências do código

- **Serviço principal:** `app/services/optimization.py` (~400 linhas)
- **Schemas:** `app/schemas/optimization.py`
- **Rotas:** `app/routers/optimization.py`
- **Benchmark:** `scripts/benchmark_paralelismo.py`
- **Testes:** `tests/test_optimization.py` (479 linhas, 22 testes)
- **Integração no app:** `app/main.py` (linha 9 e 34)

---

## 13. Checklist para apresentação

- [x] Todos os 52 testes passam (`pytest -v`)
- [x] Benchmark roda e mostra speedup real (~2.7x com 4 workers)
- [x] Servidor sobe sem erros de import (`uvicorn app.main:app --reload`)
- [x] Swagger funciona: `/optimization/suggest` e `/optimization/benchmark`
- [x] `git status` não mostra `.env` nem segredos
- [x] Documentação `docs/paralelismo.md` criada

---

*Documento gerado automaticamente como parte da Sprint 05 do CliniRotina Backend.*