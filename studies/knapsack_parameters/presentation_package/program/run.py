"""Command-line entry point for two main comparisons from a known start."""
from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from processing.io import load_case, write_log
from program.ga_core import create_random_generators, parameter_controller, run_ga, tournament_controller

# User-facing name -> internal controller profile.
# Numbers in parameters enable rules; they are not mutation probabilities.
PROFILES = {
    "parameters": {"fixed": 0, "mutation": 1, "crossover": 2, "population": 4,
                   "tournament": 8, "elitism": 16, "all": 31},
    "tournament": {"k2": "k2", "k3": "k3", "adaptive": "adaptive", "replay": "replay"},
}


def main(argv=None):
    """Parse the study block, problem, rule, budget, and output directory.

    argv=None reads command-line arguments; a list of strings allows calls
    from another Python module.
    """
    parser = argparse.ArgumentParser(description="Основні порівняння генетичного алгоритму для рюкзака")
    parser.add_argument("block", nargs="?", choices=tuple(PROFILES), help="parameters або tournament")
    parser.add_argument("--case", help="UC-s020, SC-s020, UC-s040 або SC-s040")
    parser.add_argument("--profile", help="Один профіль; без аргументу виконуються всі профілі блоку")
    parser.add_argument("--budget", type=int, default=5000, help="Нові оцінювання: від 1 до 5000")
    parser.add_argument("--output", type=Path, default=ROOT / "results", help="Каталог нових журналів")
    args = parser.parse_args(argv)
    if args.block is None:
        parser.print_help()
        return 0
    if not args.case:
        parser.error("потрібно вказати --case")
    if not 1 <= args.budget <= 5000:
        parser.error("--budget має бути від 1 до 5000")
    options = PROFILES[args.block]
    if args.profile is not None and args.profile not in options:
        parser.error("профіль: " + ", ".join(options))
    case = load_case(args.block, args.case)
    selected = [args.profile] if args.profile else list(options)
    destinations = {name: args.output / args.block / f"{args.case}-{name}-q{args.budget}.json.gz"
                    for name in selected}
    for destination in destinations.values():
        if destination.exists():
            parser.error(f"файл результату вже існує: {destination}")
        for parent in destination.parents:
            if parent.exists() and not parent.is_dir():
                parser.error(f"шлях виходу містить файл замість каталогу: {parent}")
    for name in selected:
        profile = options[name]
        if args.block == "parameters":
            controller = parameter_controller(profile)
        elif profile == "replay":
            controller = tournament_controller(profile, case["schedule"][:(args.budget + 28) // 29])
        else:
            controller = tournament_controller(profile)
        random_generators = create_random_generators(case["seed"], case["task_index"], case["start_index"])
        log = run_ga(case["problem"], case["initial_population"], controller, random_generators, args.budget)
        destination = destinations[name]
        write_log(destination, log)
        print(json.dumps({"case": args.case, "profile": name, "evaluations": log["summary"]["new_calls"],
                          "best_value": log["summary"]["best_profit"], "journal": str(destination)},
                         ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
