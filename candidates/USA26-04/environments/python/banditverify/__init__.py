"""Clean-room USA26-04 formula and ambiguity validation primitives.

This package intentionally contains no genetic algorithm or Table 1 replay.
"""

from .controller import (
    FIXTURE_STATE_PROVENANCE,
    nesterov_update,
    paper_tile_index,
    run_fixed_controller_tape,
    standard_deviation_witness,
    tile_boundary_witness,
    tie_ambiguity_witness,
)
from .objectives import OBJECTIVES, evaluate_objective
from .rewards import evaluate_reward, printed_eq2_literal

__all__ = [
    "FIXTURE_STATE_PROVENANCE",
    "OBJECTIVES",
    "evaluate_objective",
    "evaluate_reward",
    "nesterov_update",
    "paper_tile_index",
    "printed_eq2_literal",
    "run_fixed_controller_tape",
    "standard_deviation_witness",
    "tile_boundary_witness",
    "tie_ambiguity_witness",
]
