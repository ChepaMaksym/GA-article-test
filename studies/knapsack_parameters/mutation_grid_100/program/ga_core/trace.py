"""Store events in memory; file operations are handled outside the core."""
def record_candidate(search_log, candidate_event):
    """Append an evaluated-offspring event to the observation log."""
    search_log["candidates"].append(candidate_event)


def record_generation(search_log, generation_event):
    """Append a generation state without changing the population or search parameters."""
    search_log["generations"].append(generation_event)
