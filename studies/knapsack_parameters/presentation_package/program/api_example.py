"""Example of calling the shared core from another Python module."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from processing.io import load_case
from program.ga_core import create_random_generators, parameter_controller, run_ga


def main():
    # parameters selects the five-parameter study; UC-s020 is a saved problem.
    # case contains the items, known initial population, and random seed inputs.
    case = load_case("parameters", "UC-s020")
    random_generators = create_random_generators(
        case["seed"],         # Search seed: reproduces this run's random decisions.
        case["task_index"],   # Problem index: separates streams for different problems.
        case["start_index"],  # Start index: separates streams for initial population banks.
    )
    result = run_ga(
        case["problem"],             # Item count, weights, profits, and capacity.
        case["initial_population"],  # 30 known masks and their scores: masks and scores.
        parameter_controller(0),    # 0: fixed parameters; 31: adapt all five parameters.
        random_generators,          # Six separate streams for random decisions.
        budget=10,                  # Demo limit of new evaluations; a full example uses 5000.
    )
    print("Оцінювань:", result["summary"]["new_calls"])
    print("Найкраща цінність:", result["summary"]["best_profit"])


if __name__ == "__main__":
    main()
