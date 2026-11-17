"""Measure execution time separately from genetic-algorithm rules.

This module does not read fitness, change parameters, or consume random numbers.
"""
from contextlib import contextmanager
from time import perf_counter_ns


class ExecutionTimer:
    """Accumulate execution time for sequential blocks in nanoseconds."""

    def __init__(self):
        self.started_at_nanoseconds = perf_counter_ns()
        self.elapsed_nanoseconds = {
            name: 0 for name in ("validation", "selection", "variation", "evaluation",
                                 "signal", "controller", "log_assembly")
        }

    @contextmanager
    def measure(self, component_name):
        """Time the contents of a with block without affecting its execution."""
        block_started_at = perf_counter_ns()
        try:
            yield
        finally:
            self.elapsed_nanoseconds[component_name] += perf_counter_ns() - block_started_at

    def finish(self):
        """Return component timings and the total elapsed time."""
        return {**self.elapsed_nanoseconds, "total": perf_counter_ns() - self.started_at_nanoseconds}
