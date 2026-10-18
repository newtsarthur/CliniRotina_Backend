"""Rota de otimização de horários (paralelismo CPU-bound + I/O-bound)."""

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import UUID4

from app.dependencies import get_current_user
from app.services.vinculo import ids_idosos_acessiveis
from app.schemas.optimization import (
    BenchmarkResult,
    OptimizationBenchmarkRequest,
    OptimizationBenchmarkResponse,
    OptimizationRequest,
    OptimizationResponse,
    TimeSlotInput,
    TimeSlotOutput,
)
from app.services.medicamento import list_medicamentos_de
from app.services.compromisso import list_compromissos
from app.services.optimization import (
    TimeSlot,
    run_optimization,
    compute_cost,
)

router = APIRouter(prefix="/optimization", tags=["Otimização de Horários"])


# =============================================================================
# Helpers: conversão de dados do banco para TimeSlot
# =============================================================================

def _medicamento_to_slot(med: dict) -> TimeSlot:
    """Converte medicamento do Supabase para TimeSlot."""
    # medicamento tem campos: hora (int), minuto (int), id, nome_remedio
    return TimeSlot(
        hora=med.get("hora", 0),
        minuto=med.get("minuto", 0),
        fixo=False,  # medicamentos podem ser movidos
        id_ref=f"med_{med['id']}",
    )


def _compromisso_to_slot(comp: dict) -> TimeSlot:
    """Converte compromisso do Supabase para TimeSlot."""
    # compromisso tem data_hora (ISO string), tipo, especialidade, id
    dt = comp.get("data_hora")
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt)
    return TimeSlot(
        hora=dt.hour,
        minuto=dt.minute,
        fixo=True,  # consultas/exames são horários FIXOS (obrigatórios)
        id_ref=f"comp_{comp['id']}",
    )


# =============================================================================
# Rota principal: POST /optimization/suggest
# =============================================================================

@router.post("/suggest", response_model=OptimizationResponse, status_code=status.HTTP_200_OK)
async def suggest_optimization(
    body: OptimizationRequest,
    user: dict = Depends(get_current_user),
    id_idoso: Optional[UUID4] = Query(None, description="ID do idoso (opcional para IDOSO, obrigatório para CUIDADOR)"),
):
    """Sugere reorganização de horários com menos conflitos.

    - Busca medicamentos, consultas e exames do idoso em paralelo (I/O-bound)
    - Executa otimização hill-climbing com múltiplas tentativas em processos (CPU-bound)
    - Não bloqueia o event loop (roda em executor)
    - Respeita horários fixos (consultas/exames) e só move medicamentos
    - Retorna métricas completas: custo antes/depois, conflitos, tempo, workers, modo
    """
    # Resolver id_idoso com verificação de acesso
    from app.dependencies import resolver_id_idoso, garantir_acesso_idoso
    target_idoso_id = resolver_id_idoso(user, str(id_idoso) if id_idoso else None)
    garantir_acesso_idoso(user, target_idoso_id)

    # -------------------------------------------------------------------------
    # Paralelismo I/O-bound: buscar medicamentos + consultas + exames simultaneamente
    # -------------------------------------------------------------------------
    # O cliente Supabase é síncrono, mas só fazemos SELECT (leitura) - seguro para threads
    loop = asyncio.get_event_loop()

    with ThreadPoolExecutor(max_workers=3) as executor:
        fut_meds = loop.run_in_executor(executor, list_medicamentos_de, [target_idoso_id])
        fut_consultas = loop.run_in_executor(executor, list_compromissos, [target_idoso_id], "CONSULTA", None, None)
        fut_exames = loop.run_in_executor(executor, list_compromissos, [target_idoso_id], "EXAME", None, None)

        meds, consultas, exames = await asyncio.gather(fut_meds, fut_consultas, fut_exames)

    # Se o body trouxe slots customizados, usar eles (para testes/benchmark)
    # Caso contrário, buscar do banco
    if body.slots:
        slots: List[TimeSlot] = [
            TimeSlot(hora=s.hora, minuto=s.minuto, fixo=s.fixo, id_ref=s.id_ref)
            for s in body.slots
        ]
    else:
        # Converter dados do banco para TimeSlot
        slots = []
        slots.extend(_medicamento_to_slot(m) for m in meds)
        slots.extend(_compromisso_to_slot(c) for c in consultas)
        slots.extend(_compromisso_to_slot(e) for e in exames)

    # Se não há nada para otimizar, retorna vazio com métricas zeradas
    if not slots:
        return OptimizationResponse(
            original_slots=[],
            optimized_slots=[],
            cost_before=0.0,
            cost_after=0.0,
            conflicts_before=0,
            conflicts_after=0,
            execution_time_ms=0.0,
            workers_used=1,
            attempts=body.attempts,
            iterations_per_attempt=body.iterations,
            mode="sequencial (sem dados)",
        )

    # -------------------------------------------------------------------------
    # Paralelismo CPU-bound: otimização em processos (fora do event loop)
    # -------------------------------------------------------------------------
    def _run_opt():
        return run_optimization(
            slots=slots,
            attempts=body.attempts,
            iterations=body.iterations,
            workers=body.workers,
        )

    result = await loop.run_in_executor(None, _run_opt)

    # Converter para response model
    return OptimizationResponse(
        original_slots=[
            TimeSlotOutput(hora=s.hora, minuto=s.minuto, fixo=s.fixo, id_ref=s.id_ref)
            for s in result.original_slots
        ],
        optimized_slots=[
            TimeSlotOutput(hora=s.hora, minuto=s.minuto, fixo=s.fixo, id_ref=s.id_ref)
            for s in result.optimized_slots
        ],
        cost_before=result.cost_before,
        cost_after=result.cost_after,
        conflicts_before=result.conflicts_before,
        conflicts_after=result.conflicts_after,
        execution_time_ms=result.execution_time_ms,
        workers_used=result.workers_used,
        attempts=result.attempts,
        iterations_per_attempt=result.iterations_per_attempt,
        mode=result.mode,
    )


# =============================================================================
# Rota de benchmark: POST /optimization/benchmark
# =============================================================================

@router.post("/benchmark", response_model=OptimizationBenchmarkResponse, status_code=status.HTTP_200_OK)
async def benchmark_optimization(
    body: OptimizationBenchmarkRequest,
    user: dict = Depends(get_current_user),
    id_idoso: Optional[UUID4] = Query(None),
):
    """Executa benchmark comparativo: sequencial (1 worker) vs paralelo (N workers).

    Útil para demonstrar o ganho de paralelismo na apresentação.
    Repete cada configuração N vezes e retorna média.
    """
    from app.dependencies import resolver_id_idoso, garantir_acesso_idoso
    target_idoso_id = resolver_id_idoso(user, str(id_idoso) if id_idoso else None)
    garantir_acesso_idoso(user, target_idoso_id)

    # Buscar dados do banco (mesmo paralelismo I/O)
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=3) as executor:
        fut_meds = loop.run_in_executor(executor, list_medicamentos_de, [target_idoso_id])
        fut_consultas = loop.run_in_executor(executor, list_compromissos, [target_idoso_id], "CONSULTA", None, None)
        fut_exames = loop.run_in_executor(executor, list_compromissos, [target_idoso_id], "EXAME", None, None)
        meds, consultas, exames = await asyncio.gather(fut_meds, fut_consultas, fut_exames)

    slots: List[TimeSlot] = []
    slots.extend(_medicamento_to_slot(m) for m in meds)
    slots.extend(_compromisso_to_slot(c) for c in consultas)
    slots.extend(_compromisso_to_slot(e) for e in exames)

    if not slots:
        raise HTTPException(status_code=400, detail="Nenhum horário encontrado para benchmark")

    # Se body trouxe slots customizados, usar eles
    if body.slots:
        fixed_from_db = [s for s in slots if s.fixo]
        movable_from_body = [TimeSlot(hora=s.hora, minuto=s.minuto, fixo=s.fixo, id_ref=s.id_ref) for s in body.slots if not s.fixo]
        slots = fixed_from_db + movable_from_body

    # Executar benchmark para cada configuração de workers
    results: List[BenchmarkResult] = []

    for workers in body.workers_list:
        times: List[float] = []
        costs: List[float] = []
        conflicts_list: List[int] = []

        for _ in range(body.repetitions):
            start = time.perf_counter()
            result = run_optimization(
                slots=slots,
                attempts=body.attempts,
                iterations=body.iterations,
                workers=workers,
            )
            elapsed_ms = (time.perf_counter() - start) * 1000

            times.append(elapsed_ms)
            costs.append(result.cost_after)
            conflicts_list.append(result.conflicts_after)

        avg_time = sum(times) / len(times)
        avg_cost = sum(costs) / len(costs)
        avg_conflicts = sum(conflicts_list) / len(conflicts_list)
        mode = "paralelo" if workers > 1 else "sequencial"

        results.append(BenchmarkResult(
            workers=workers,
            mode=mode,
            execution_time_ms=round(avg_time, 2),
            cost_after=round(avg_cost, 2),
            conflicts_after=round(avg_conflicts),
        ))

    # Melhor configuração = menor tempo (ou menor custo se empate)
    best = min(results, key=lambda r: (r.execution_time_ms, r.cost_after))

    # Speedup vs sequencial (workers=1)
    sequential_result = next((r for r in results if r.workers == 1), None)
    speedup = 1.0
    if sequential_result and best.execution_time_ms > 0:
        speedup = sequential_result.execution_time_ms / best.execution_time_ms

    return OptimizationBenchmarkResponse(
        results=results,
        best_config=best,
        speedup_vs_sequential=round(speedup, 2),
    )


# Import local para evitar circular
from datetime import datetime