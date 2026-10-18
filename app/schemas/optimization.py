"""Schemas Pydantic para o módulo de otimização."""

from typing import List, Literal, Optional
from pydantic import BaseModel, Field, field_validator


class TimeSlotInput(BaseModel):
    """Horário de entrada para otimização."""
    hora: int = Field(..., ge=0, le=23, description="Hora (0-23)")
    minuto: int = Field(..., ge=0, le=59, description="Minuto (0-59)")
    fixo: bool = Field(..., description="True se horário obrigatório (não pode ser alterado)")
    id_ref: str = Field(..., min_length=1, max_length=100, description="ID de referência (medicamento/consulta/exame)")


class OptimizationRequest(BaseModel):
    """Requisição de otimização de horários."""
    slots: List[TimeSlotInput] = Field(
        default_factory=list,
        max_length=100,
        description="Lista de horários a otimizar (máx 100 para evitar abuso). Se vazio, busca do banco."
    )
    attempts: Optional[int] = Field(
        default=8,
        ge=1,
        le=50,
        description="Número de tentativas independentes (seeds diferentes)"
    )
    iterations: Optional[int] = Field(
        default=50,
        ge=1,
        le=500,
        description="Iterações de hill climbing por tentativa"
    )
    workers: Optional[int] = Field(
        default=None,
        ge=1,
        le=16,
        description="Número de workers paralelos (None = auto, limitado por CPU)"
    )

    @field_validator("slots")
    @classmethod
    def validate_no_duplicate_fixed_times(cls, v: List[TimeSlotInput]) -> List[TimeSlotInput]:
        """Horários fixos não podem ter duplicatas exatas (conflito irreconciliável)."""
        fixed_times = [(s.hora, s.minuto) for s in v if s.fixo]
        if len(fixed_times) != len(set(fixed_times)):
            raise ValueError("Horários fixos não podem ter duplicatas (conflito irreconciliável)")
        return v

    @field_validator("slots")
    @classmethod
    def validate_at_least_one_movable(cls, v: List[TimeSlotInput]) -> List[TimeSlotInput]:
        """Pelo menos um horário deve ser móvel (não-fixo) para otimização fazer sentido."""
        # Só validar se a lista não estiver vazia (vazia = buscar do banco)
        if v and all(s.fixo for s in v):
            raise ValueError("Pelo menos um horário deve ser não-fixo (móvel) para otimização")
        return v


class TimeSlotOutput(BaseModel):
    """Horário de saída (otimizado)."""
    hora: int
    minuto: int
    fixo: bool
    id_ref: str

    def to_str(self) -> str:
        return f"{self.hora:02d}:{self.minuto:02d}{' (fixo)' if self.fixo else ''}"


class OptimizationResponse(BaseModel):
    """Resposta da otimização com métricas completas."""
    original_slots: List[TimeSlotOutput]
    optimized_slots: List[TimeSlotOutput]
    cost_before: float
    cost_after: float
    conflicts_before: int
    conflicts_after: int
    execution_time_ms: float
    workers_used: int
    attempts: int
    iterations_per_attempt: int
    mode: Literal["paralelo", "sequencial", "sequencial (fallback: erro no pool)", "sequencial (sem slots móveis)", "sequencial (sem dados)"]

    # Propriedades derivadas para conveniência do frontend
    @property
    def cost_reduction_pct(self) -> float:
        if self.cost_before == 0:
            return 0.0
        return ((self.cost_before - self.cost_after) / self.cost_before) * 100

    @property
    def conflicts_reduction(self) -> int:
        return self.conflicts_before - self.conflicts_after

    @property
    def speedup_info(self) -> str:
        return f"{self.workers_used} worker(s), {self.attempts} tentativa(s), {self.iterations_per_attempt} iteração(ões) cada"


class OptimizationBenchmarkRequest(BaseModel):
    """Requisição para benchmark comparativo (sequencial vs paralelo)."""
    slots: List[TimeSlotInput] = Field(
        default_factory=list,
        max_length=100,
        description="Lista de horários para benchmark. Se vazio, busca do banco."
    )
    attempts: int = Field(default=8, ge=1, le=50)
    iterations: int = Field(default=50, ge=1, le=500)
    workers_list: List[int] = Field(
        default=[1, 2, 4, 8],
        description="Lista de workers para testar (1 = sequencial)"
    )
    repetitions: int = Field(default=3, ge=1, le=10, description="Repetições por configuração")


class BenchmarkResult(BaseModel):
    """Resultado de uma execução de benchmark."""
    workers: int
    mode: str
    execution_time_ms: float
    cost_after: float
    conflicts_after: int


class OptimizationBenchmarkResponse(BaseModel):
    """Resposta do benchmark comparativo."""
    results: List[BenchmarkResult]
    best_config: BenchmarkResult
    speedup_vs_sequential: float