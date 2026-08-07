"""Clean-room Python reference for the GESMR direct optimizer."""

from .benchmarks import BENCHMARKS, get_benchmark
from .core import (
    GESMRConfig,
    RandomTape,
    RunResult,
    StepResult,
    gesmr_step,
    initial_mutation_rates,
    run_gesmr,
)

__all__ = [
    "BENCHMARKS",
    "GESMRConfig",
    "RandomTape",
    "RunResult",
    "StepResult",
    "gesmr_step",
    "get_benchmark",
    "initial_mutation_rates",
    "run_gesmr",
]
