"""Independent transcription of the pinned author's *outer* CHC-QX loop.

This module is a source-compatibility reference, not the corrected experiment.
The supplied Evolution class owns progressive instance selection and native CHC.
No initial full checkpoint, safety cap, test restriction, sparsity tie-break, or
lambda optimizer is silently added to the author's controller here.
"""
from __future__ import annotations

import copy
from typing import Any, Callable

import numpy as np
import pandas as pd


def source_compatible_qx(
    evolution: Any,
    baseline_individual: Any,
    f: int = 10,
    n_individual: int = 10,
    f_no_change: int = 2,
    population_size: int = 50,
    verbose: int = 0,
    *,
    clock: Callable[[], float],
) -> tuple[Any, list[Any]]:
    """Return the author's improvement log and controlled full-data models.

    The source calls CHC afresh every block: population and d survive, while
    that function's offspring-history is rebuilt from the current population.
    The outer full-evaluation history survives all blocks. Its entries retain
    the same references as the source; native CHC clones before mating them.
    Full scores must not overwrite individuals' approximate DEAP fitness.
    """
    gaqx_log_df = pd.DataFrame(columns=["ind", "time", "fitness"])
    start = clock()
    selected_instances, baseline_full_data = evolution.select_instances(
        n_individual, baseline_individual
    )
    if not population_size:
        population_size = baseline_individual.X_train.shape[1]
    gaqx_individual = copy.deepcopy(baseline_individual)
    gaqx_individual.set_instances(selected_instances)
    print("Meta-model sample size:", len(selected_instances))
    task = "feature_selection"
    target_dataset = "validation"
    ind_size = gaqx_individual.X_train.shape[1]
    toolbox = evolution.create_toolbox(
        task, target_dataset, gaqx_individual, baseline_full_data
    )
    population = evolution.create_population(population_size, ind_size)
    evaluated_population: list[Any] = []
    best = 0
    no_change = 0
    d = ind_size // 4
    generation = 0
    while no_change < f_no_change:
        no_change += 1
        _, population, d = evolution.CHC(
            gaqx_individual, toolbox, d, population, max_generations=f, verbose=0
        )
        generation += f
        for ind in population:
            if ind not in evaluated_population:
                evaluated_population.append(ind)
                fitness = evolution.evaluate(
                    ind, task, target_dataset, baseline_individual
                )[0]
                if fitness > best:
                    gaqx_time = clock() - start
                    gaqx_log_df.loc[len(gaqx_log_df)] = [ind, gaqx_time, fitness]
                    if verbose:
                        print(
                            "Best Individual = ", np.round(fitness, 4),
                            ", Gen = ", generation, "\r", end="",
                        )
                    best = fitness
                    no_change = 0
    return gaqx_log_df, baseline_full_data
