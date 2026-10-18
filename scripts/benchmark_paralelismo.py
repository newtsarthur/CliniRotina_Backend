#!/usr/bin/env python3
"""Benchmark comparativo: otimização sequencial vs paralela.

Este script roda a mesma entrada nos dois modos (1 worker vs N workers),
repete várias vezes e imprime uma tabela com tempos, custo final e speedup.

Uso:
    python scripts/benchmark_paralelismo.py [--attempts N] [--iterations N] [--workers N] [--repetitions N]
"""

import argparse
import os
import sys
import time
from statistics import mean, stdev
from typing import List

# Adicionar o diretório raiz ao path para importar app.services.optimization
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.optimization import (
    TimeSlot,
    run_optimization,
    compute_cost,
    DEFAULT_ATTEMPTS,
    DEFAULT_ITERATIONS,
    MAX_WORKERS,
)


def generate_test_scenario(num_medicamentos: int = 8, num_consultas: int = 3, num_exames: int = 2) -> List[TimeSlot]:
    """Gera cenário de teste realista com medicamentos (móveis) e consultas/exames (fixos)."""
    import random
    random.seed(12345)  # Seed fixa para reprodutibilidade

    slots: List[TimeSlot] = []

    # Medicamentos (não-fixos) - distribuídos ao longo do dia com alguns conflitos
    med_times = [
        (7, 0), (7, 10), (7, 25),  # Conflito matinal
        (12, 0), (12, 5),          # Conflito almoço
        (18, 0), (18, 12),         # Conflito noite
        (22, 0),                   # Sozinho
    ]
    for i, (h, m) in enumerate(med_times[:num_medicamentos]):
        slots.append(TimeSlot(hora=h, minuto=m, fixo=False, id_ref=f"med_{i}"))

    # Consultas (fixos) - horários obrigatórios
    consulta_times = [
        (9, 30), (14, 0), (16, 45),
    ]
    for i, (h, m) in enumerate(consulta_times[:num_consultas]):
        slots.append(TimeSlot(hora=h, minuto=m, fixo=True, id_ref=f"comp_consulta_{i}"))

    # Exames (fixos)
    exame_times = [
        (8, 0), (10, 30),
    ]
    for i, (h, m) in enumerate(exame_times[:num_exames]):
        slots.append(TimeSlot(hora=h, minuto=m, fixo=True, id_ref=f"comp_exame_{i}"))

    return slots


def run_benchmark(
    slots: List[TimeSlot],
    attempts: int,
    iterations: int,
    workers: int,
    repetitions: int,
) -> dict:
    """Executa benchmark para uma configuração específica."""
    times = []
    costs = []
    conflicts = []

    for rep in range(repetitions):
        start = time.perf_counter()
        result = run_optimization(
            slots=slots,
            attempts=attempts,
            iterations=iterations,
            workers=workers,
        )
        elapsed_ms = (time.perf_counter() - start) * 1000

        times.append(elapsed_ms)
        costs.append(result.cost_after)
        conflicts.append(result.conflicts_after)

        print(f"  Rep {rep + 1}/{repetitions}: {elapsed_ms:.1f}ms, cost={result.cost_after:.1f}, conflicts={result.conflicts_after}, mode={result.mode}")

    return {
        "workers": workers,
        "mode": "paralelo" if workers > 1 else "sequencial",
        "times": times,
        "avg_time": mean(times),
        "stdev_time": stdev(times) if len(times) > 1 else 0.0,
        "avg_cost": mean(costs),
        "avg_conflicts": mean(conflicts),
    }


def print_results_table(results: List[dict], baseline_workers: int = 1):
    """Imprime tabela formatada dos resultados."""
    print("\n" + "=" * 100)
    print("RESULTADOS DO BENCHMARK")
    print("=" * 100)

    # Encontrar baseline (sequencial)
    baseline = next((r for r in results if r["workers"] == baseline_workers), None)
    baseline_time = baseline["avg_time"] if baseline else 1.0

    header = f"{'Workers':>8} | {'Modo':>12} | {'Tempo Médio (ms)':>16} | {'Desvio (ms)':>12} | {'Custo Médio':>12} | {'Conflitos':>10} | {'Speedup':>8}"
    print(header)
    print("-" * len(header))

    for r in results:
        speedup = baseline_time / r["avg_time"] if r["avg_time"] > 0 else 0.0
        print(f"{r['workers']:>8} | {r['mode']:>12} | {r['avg_time']:>16.2f} | {r['stdev_time']:>12.2f} | {r['avg_cost']:>12.2f} | {r['avg_conflicts']:>10.1f} | {speedup:>7.2f}x")

    print("-" * len(header))

    # Melhor configuração
    best = min(results, key=lambda r: r["avg_time"])
    print(f"\n✅ Melhor configuração: {best['workers']} worker(s) ({best['mode']}) - {best['avg_time']:.1f}ms médio")
    print(f"   Speedup vs sequencial: {baseline_time / best['avg_time']:.2f}x")
    print(f"   Custo final: {best['avg_cost']:.1f} | Conflitos: {best['avg_conflicts']:.1f}")

    # Análise de custo (qualidade da solução)
    print("\n📊 ANÁLISE DE QUALIDADE (custo final):")
    for r in results:
        print(f"   {r['workers']} worker(s): custo={r['avg_cost']:.1f}, conflitos={r['avg_conflicts']:.1f}")

    # Verificar se paralelo manteve ou melhorou qualidade
    parallel_results = [r for r in results if r["workers"] > 1]
    if parallel_results:
        best_parallel_cost = min(r["avg_cost"] for r in parallel_results)
        if best_parallel_cost <= baseline["avg_cost"] + 1e-9:
            print("\n✅ Paralelismo manteve ou melhorou qualidade da solução (custo <= sequencial)")
        else:
            print(f"\n⚠️ Paralelismo teve custo ligeiramente maior ({best_parallel_cost:.1f} vs {baseline['avg_cost']:.1f}) - variação normal de busca estocástica")


def main():
    parser = argparse.ArgumentParser(description="Benchmark otimização sequencial vs paralela")
    parser.add_argument("--attempts", type=int, default=DEFAULT_ATTEMPTS, help="Tentativas independentes")
    parser.add_argument("--iterations", type=int, default=DEFAULT_ITERATIONS, help="Iterações por tentativa")
    parser.add_argument("--workers", type=int, default=MAX_WORKERS, help="Máximo de workers para testar")
    parser.add_argument("--repetitions", type=int, default=3, help="Repetições por configuração")
    parser.add_argument("--medicamentos", type=int, default=8, help="Número de medicamentos")
    parser.add_argument("--consultas", type=int, default=3, help="Número de consultas (fixas)")
    parser.add_argument("--exames", type=int, default=2, help="Número de exames (fixos)")
    parser.add_argument("--cpu-limit", type=int, help="Limitar CPU count para simular serverless")

    args = parser.parse_args()

    # Simular limite de CPU se solicitado (útil para testar fallback)
    if args.cpu_limit:
        import app.services.optimization as opt_module
        original_cpu_count = os.cpu_count
        os.cpu_count = lambda: args.cpu_limit
        print(f"🔧 Simulando CPU count = {args.cpu_limit}")

    print("🔬 BENCHMARK DE PARALELISMO - CliniRotina Otimização")
    print("=" * 100)
    print(f"Configuração: attempts={args.attempts}, iterations={args.iterations}, repetitions={args.repetitions}")
    print(f"Cenário: {args.medicamentos} medicamentos, {args.consultas} consultas, {args.exames} exames")
    print(f"CPUs disponíveis: {os.cpu_count()}")
    print(f"Workers máximos testados: {args.workers}")

    # Gerar cenário de teste
    slots = generate_test_scenario(args.medicamentos, args.consultas, args.exames)
    print(f"\n📋 Slots iniciais ({len(slots)} total):")
    for s in slots:
        print(f"   {s}")

    # Custo inicial
    initial_cost, initial_conflicts = compute_cost(slots, slots)
    print(f"\n📈 Custo inicial: {initial_cost:.1f} | Conflitos: {initial_conflicts}")

    # Configurações de workers para testar
    cpu_count = os.cpu_count() or 1
    max_workers = min(args.workers, cpu_count)
    worker_configs = [1] + [w for w in [2, 4, 8, 16] if w <= max_workers]
    # Remover duplicatas mantendo ordem
    worker_configs = list(dict.fromkeys(worker_configs))

    print(f"\n🚀 Testando configurações: {worker_configs}")

    # Executar benchmarks
    all_results = []
    for workers in worker_configs:
        print(f"\n⏱️  Workers={workers} ({'paralelo' if workers > 1 else 'sequencial'}):")
        result = run_benchmark(slots, args.attempts, args.iterations, workers, args.repetitions)
        all_results.append(result)

    # Imprimir tabela
    print_results_table(all_results)

    print("\n" + "=" * 100)
    print("NOTAS:")
    print("- Speedup não é linear devido a overhead de criação de processos e GIL-free CPU work")
    print("- Qualidade da solução (custo) pode variar entre runs por natureza estocástica do hill climbing")
    print("- Em ambiente serverless (Vercel), cpu_count pode ser 1 → fallback sequencial automático")
    print("=" * 100)


if __name__ == "__main__":
    main()