"""Módulo de otimização de lembretes com paralelismo (CPU-bound).

Implementa busca local (hill climbing) com múltiplas tentativas independentes
executadas em paralelo via ProcessPoolExecutor. Inclui fallback automático
para execução sequencial (ex.: ambiente serverless com 1 núcleo).
"""

from __future__ import annotations

import os
import time
import random
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from typing import List, Tuple, Set, Optional
from datetime import datetime, timedelta


# =============================================================================
# Tipos e estruturas de dados (simples, serializáveis para multiprocessing)
# =============================================================================

@dataclass(frozen=True)
class TimeSlot:
    """Representa um horário agendado."""
    hora: int        # 0-23
    minuto: int      # 0-59
    fixo: bool       # True = horário obrigatório (não pode ser movido)
    id_ref: str      # Identificador original (medicamento/consulta/exame)

    def total_minutes(self) -> int:
        return self.hora * 60 + self.minuto

    def to_tuple(self) -> Tuple[int, int]:
        return (self.hora, self.minuto)

    @classmethod
    def from_tuple(cls, t: Tuple[int, int], fixo: bool, id_ref: str) -> "TimeSlot":
        return cls(hora=t[0], minuto=t[1], fixo=fixo, id_ref=id_ref)

    def __str__(self) -> str:
        return f"{self.hora:02d}:{self.minuto:02d}{' (fixo)' if self.fixo else ''}"


@dataclass
class OptimizationResult:
    """Resultado de uma única execução de otimização."""
    slots: List[TimeSlot]
    cost: float
    conflicts: int


@dataclass
class OptimizationOutput:
    """Resultado final retornado pela API."""
    original_slots: List[TimeSlot]
    optimized_slots: List[TimeSlot]
    cost_before: float
    cost_after: float
    conflicts_before: int
    conflicts_after: int
    execution_time_ms: float
    workers_used: int
    attempts: int
    iterations_per_attempt: int
    mode: str  # "paralelo" | "sequencial"


# =============================================================================
# Função de custo (pura, sem efeitos colaterais, serializável)
# =============================================================================

CONFLICT_WINDOW_MINUTES = 15  # Janela de "quase conflito"


def compute_cost(slots: List[TimeSlot], original_slots: List[TimeSlot]) -> Tuple[float, int]:
    """Calcula o custo total de uma configuração de horários.

    Penalizações:
    - Conflito exato (mesmo horário): +1000 por par
    - Quase conflito (< 15 min): +100 por par
    - Desvio do horário original (apenas não-fixos): +1 por minuto de diferença

    Returns:
        (custo_total, numero_conflitos_exatos)
    """
    cost = 0.0
    conflicts = 0
    n = len(slots)

    # Mapa de índice original para calcular desvio
    original_by_id = {s.id_ref: s for s in original_slots}

    # Verificar pares para conflitos
    for i in range(n):
        si = slots[i]
        ti = si.total_minutes()

        # Desvio do original (só para não-fixos)
        if not si.fixo:
            orig = original_by_id.get(si.id_ref)
            if orig:
                cost += abs(ti - orig.total_minutes())

        for j in range(i + 1, n):
            sj = slots[j]
            tj = sj.total_minutes()
            diff = abs(ti - tj)

            if diff == 0:
                # Conflito exato
                cost += 1000.0
                conflicts += 1
            elif diff < CONFLICT_WINDOW_MINUTES:
                # Quase conflito
                cost += 100.0

    return cost, conflicts


# =============================================================================
# Função worker (nível de módulo = serializável para multiprocessing)
# =============================================================================

def _worker_hill_climb(
    seed: int,
    slots_data: List[Tuple[int, int, bool, str]],
    original_slots_data: List[Tuple[int, int, bool, str]],
    iterations: int,
) -> OptimizationResult:
    """Executa uma tentativa de hill climbing com seed determinística.

    Args:
        seed: Seed para random (reprodutibilidade)
        slots_data: Lista de (hora, minuto, fixo, id_ref) - estado inicial
        original_slots_data: Lista de (hora, minuto, fixo, id_ref) - horários originais
        iterations: Número de iterações de busca local

    Returns:
        OptimizationResult com melhor configuração encontrada
    """
    random.seed(seed)

    # Reconstruir slots
    slots = [TimeSlot.from_tuple((h, m), fixo, id_ref) for h, m, fixo, id_ref in slots_data]
    original_slots = [TimeSlot.from_tuple((h, m), fixo, id_ref) for h, m, fixo, id_ref in original_slots_data]

    # Índices dos slots móveis (não fixos)
    movable_indices = [i for i, s in enumerate(slots) if not s.fixo]

    if not movable_indices:
        # Nada a otimizar
        cost, conflicts = compute_cost(slots, original_slots)
        return OptimizationResult(slots=slots, cost=cost, conflicts=conflicts)

    current_slots = slots[:]
    current_cost, current_conflicts = compute_cost(current_slots, original_slots)

    best_slots = current_slots[:]
    best_cost = current_cost
    best_conflicts = current_conflicts

    # Hill climbing: tentar mover cada slot móvel para horários vizinhos
    for _ in range(iterations):
        improved = False

        # Embaralhar ordem de tentativa para variar a busca
        random.shuffle(movable_indices)

        for idx in movable_indices:
            slot = current_slots[idx]
            current_minutes = slot.total_minutes()

            # Gerar vizinhos: ±5, ±10, ±15, ±30, ±60 minutos (dentro do dia)
            neighbor_offsets = [-60, -30, -15, -10, -5, 5, 10, 15, 30, 60]
            random.shuffle(neighbor_offsets)

            for offset in neighbor_offsets:
                new_minutes = current_minutes + offset
                if new_minutes < 0 or new_minutes >= 24 * 60:
                    continue

                new_hora = new_minutes // 60
                new_minuto = new_minutes % 60

                # Tentar mover
                trial_slots = current_slots[:]
                trial_slots[idx] = TimeSlot(
                    hora=new_hora,
                    minuto=new_minuto,
                    fixo=slot.fixo,
                    id_ref=slot.id_ref
                )

                trial_cost, trial_conflicts = compute_cost(trial_slots, original_slots)

                if trial_cost < current_cost:
                    current_slots = trial_slots
                    current_cost = trial_cost
                    current_conflicts = trial_conflicts
                    improved = True
                    break  # Aceita a primeira melhoria (first-improvement)

            if improved:
                break  # Reinicia varredura dos slots

        # Atualizar melhor global
        if current_cost < best_cost:
            best_slots = current_slots[:]
            best_cost = current_cost
            best_conflicts = current_conflicts

        # Se não melhorou nessa iteração, perturbação aleatória para escapar de ótimo local
        if not improved and random.random() < 0.1:
            idx = random.choice(movable_indices)
            slot = current_slots[idx]
            # Salto aleatório maior
            jump = random.randint(-120, 120)
            new_minutes = slot.total_minutes() + jump
            new_minutes = max(0, min(23 * 60 + 59, new_minutes))
            current_slots[idx] = TimeSlot(
                hora=new_minutes // 60,
                minuto=new_minutes % 60,
                fixo=slot.fixo,
                id_ref=slot.id_ref
            )
            current_cost, current_conflicts = compute_cost(current_slots, original_slots)

    return OptimizationResult(slots=best_slots, cost=best_cost, conflicts=best_conflicts)


# =============================================================================
# Orquestração principal (chamada pela rota da API)
# =============================================================================

DEFAULT_ATTEMPTS = 8
DEFAULT_ITERATIONS = 50
MAX_WORKERS = min(8, os.cpu_count() or 1)


def _slots_to_data(slots: List[TimeSlot]) -> List[Tuple[int, int, bool, str]]:
    """Converte lista de TimeSlot para tuplas serializáveis."""
    return [(s.hora, s.minuto, s.fixo, s.id_ref) for s in slots]


def _data_to_slots(data: List[Tuple[int, int, bool, str]]) -> List[TimeSlot]:
    """Converte tuplas serializáveis de volta para TimeSlot."""
    return [TimeSlot.from_tuple((h, m), fixo, id_ref) for h, m, fixo, id_ref in data]


def run_optimization(
    slots: List[TimeSlot],
    attempts: int = DEFAULT_ATTEMPTS,
    iterations: int = DEFAULT_ITERATIONS,
    workers: Optional[int] = None,
) -> OptimizationOutput:
    """Executa otimização paralela (ou sequencial como fallback).

    Args:
        slots: Horários iniciais (incluindo fixos)
        attempts: Número de tentativas independentes (seeds diferentes)
        iterations: Iterações de hill climbing por tentativa
        workers: Número de processos (None = auto, limitado por cpu_count)

    Returns:
        OptimizationOutput com melhor resultado e metadados
    """
    start_time = time.perf_counter()

    # Preparar dados serializáveis
    slots_data = _slots_to_data(slots)
    original_slots_data = slots_data[:]  # Cópia para cálculo de desvio

    # Validar: pelo menos um slot não-fixo para otimizar
    if all(s.fixo for s in slots):
        cost, conflicts = compute_cost(slots, slots)
        return OptimizationOutput(
            original_slots=slots,
            optimized_slots=slots,
            cost_before=cost,
            cost_after=cost,
            conflicts_before=conflicts,
            conflicts_after=conflicts,
            execution_time_ms=0.0,
            workers_used=1,
            attempts=attempts,
            iterations_per_attempt=iterations,
            mode="sequencial (sem slots móveis)",
        )

    # Determinar workers efetivos
    cpu_count = os.cpu_count() or 1
    effective_workers = min(workers or cpu_count, cpu_count, attempts)
    effective_workers = max(1, effective_workers)

    # Seeds determinísticas para reprodutibilidade
    base_seed = 42
    seeds = [base_seed + i * 1000 for i in range(attempts)]

    best_result: Optional[OptimizationResult] = None
    mode = "paralelo"

    # Tentar paralelismo
    if effective_workers > 1:
        try:
            with ProcessPoolExecutor(max_workers=effective_workers) as executor:
                futures = [
                    executor.submit(_worker_hill_climb, seed, slots_data, original_slots_data, iterations)
                    for seed in seeds
                ]
                results = [f.result() for f in as_completed(futures)]
        except Exception:
            # Fallback: execução sequencial
            effective_workers = 1
            mode = "sequencial (fallback: erro no pool)"
            results = [
                _worker_hill_climb(seed, slots_data, original_slots_data, iterations)
                for seed in seeds
            ]
    else:
        # Execução sequencial (1 worker ou forçado)
        mode = "sequencial"
        results = [
            _worker_hill_climb(seed, slots_data, original_slots_data, iterations)
            for seed in seeds
        ]

    # Selecionar melhor resultado (menor custo)
    best_result = min(results, key=lambda r: r.cost)

    # Custo/conflitos do estado original
    original_cost, original_conflicts = compute_cost(slots, slots)

    execution_time_ms = (time.perf_counter() - start_time) * 1000

    return OptimizationOutput(
        original_slots=slots,
        optimized_slots=best_result.slots,
        cost_before=original_cost,
        cost_after=best_result.cost,
        conflicts_before=original_conflicts,
        conflicts_after=best_result.conflicts,
        execution_time_ms=execution_time_ms,
        workers_used=effective_workers,
        attempts=attempts,
        iterations_per_attempt=iterations,
        mode=mode,
    )