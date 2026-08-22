from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

GSEMO_BLOB = "2693144bcfccff902343a02c6c8e48d7dd263257"
MAIN_BLOB = "22025e4680da85c98e3bb5ea30db8334ca25dff3"


def git_blob_sha1(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode()
    return hashlib.sha1(header + data).hexdigest()


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one preimage, found {count}")
    return text.replace(old, new, 1)


V2_CLASSES = r'''
    // EU26-27 HYBRID v2 research extensions. The inherited TwoRate mutation
    // controller is unchanged. Only offspring population-size control is added.
    template <typename SolutionType>
    struct HybridRollback : TwoRate<SolutionType>
    {
        using TwoRate<SolutionType>::TwoRate;

        void setup_problem(const std::shared_ptr<ioh::problem::IntegerSingleObjective> &problem,
                           const std::vector<SolutionType> &pareto_front,
                           const SolutionType &hv) override
        {
            TwoRate<SolutionType>::setup_problem(problem, pareto_front, hv);
            lambda_real = std::max(static_cast<double>(this->lambda), lambda_floor);
            lambda_base = lambda_real;
            bad_count = 0;
            delta = delta_initial;
            this->lambda = rounded_lambda(lambda_real);
        }

        void adapt(const std::vector<SolutionType> &pareto_front,
                   const std::vector<SolutionType> &new_population) override
        {
            const auto metrics = this->population_stats(pareto_front, new_population);
            const double before = this->pareto_metric(pareto_front);
            const double best = *std::max_element(metrics.begin(), metrics.end());
            const bool strict_success = best > before;

            // Preserve the complete paper-era TwoRate r update, including RNG.
            TwoRate<SolutionType>::adapt(pareto_front, new_population);

            if (strict_success)
            {
                lambda_real = std::max(lambda_real / update_factor, lambda_floor);
                lambda_base = lambda_real;
                bad_count = 0;
                delta = delta_initial;
            }
            else
            {
                bad_count += 1;
                if (bad_count == delta)
                {
                    bad_count = 0;
                    delta += 1;
                }
                lambda_real = std::min(
                    lambda_base * std::pow(update_factor,
                                           static_cast<double>(bad_count) / (u - 1.0)),
                    static_cast<double>(this->n));
            }

            this->lambda = rounded_lambda(lambda_real);
            std::cout << "HYBRID_V2_ROLLBACK " << lambda_real << " " << this->lambda
                      << " " << strict_success << " " << lambda_base << " "
                      << bad_count << " " << delta << std::endl;
        }

    private:
        int rounded_lambda(const double value) const
        {
            return std::max(static_cast<int>(lambda_floor),
                            std::min(this->n, static_cast<int>(std::floor(value + 0.5))));
        }

        double lambda_real = 10.0;
        double lambda_base = 10.0;
        int bad_count = 0;
        int delta = 10;
        const double update_factor = 1.5;
        const double u = 5.0;
        const double lambda_floor = 10.0;
        const int delta_initial = 10;
    };

    template <typename SolutionType>
    struct HybridFloor : TwoRate<SolutionType>
    {
        using TwoRate<SolutionType>::TwoRate;

        void setup_problem(const std::shared_ptr<ioh::problem::IntegerSingleObjective> &problem,
                           const std::vector<SolutionType> &pareto_front,
                           const SolutionType &hv) override
        {
            TwoRate<SolutionType>::setup_problem(problem, pareto_front, hv);
            lambda_real = std::max(static_cast<double>(this->lambda), lambda_floor);
            this->lambda = rounded_lambda(lambda_real);
        }

        void adapt(const std::vector<SolutionType> &pareto_front,
                   const std::vector<SolutionType> &new_population) override
        {
            const auto metrics = this->population_stats(pareto_front, new_population);
            const double before = this->pareto_metric(pareto_front);
            const double best = *std::max_element(metrics.begin(), metrics.end());
            const bool strict_success = best > before;

            TwoRate<SolutionType>::adapt(pareto_front, new_population);

            if (strict_success)
                lambda_real = std::max(lambda_real / update_factor, lambda_floor);
            else
                lambda_real = std::min(lambda_real * std::pow(update_factor, 0.25),
                                       static_cast<double>(this->n));

            this->lambda = rounded_lambda(lambda_real);
            std::cout << "HYBRID_V2_FLOOR " << lambda_real << " " << this->lambda
                      << " " << strict_success << std::endl;
        }

    private:
        int rounded_lambda(const double value) const
        {
            return std::max(static_cast<int>(lambda_floor),
                            std::min(this->n, static_cast<int>(std::floor(value + 0.5))));
        }

        double lambda_real = 10.0;
        const double update_factor = 1.5;
        const double lambda_floor = 10.0;
    };

'''


def patch_gsemo(path: Path) -> None:
    raw = path.read_bytes()
    observed = git_blob_sha1(raw)
    if observed != GSEMO_BLOB:
        raise RuntimeError(f"gsemo.hpp preimage {observed} != {GSEMO_BLOB}")
    text = raw.decode()

    marker = "    template <typename SolutionType>\n    struct LogNormal : Strategy<SolutionType>\n"
    text = replace_once(text, marker, V2_CLASSES + marker, "v2 class insertion")

    selector = '''        else if (name == "TwoRate")\n            return std::make_unique<adaptation::TwoRate<T> >(pm, lambda, adapt_metric);\n'''
    selector_new = selector + '''        else if (name == "HybridRollback")\n            return std::make_unique<adaptation::HybridRollback<T> >(pm, lambda, adapt_metric);\n        else if (name == "HybridFloor")\n            return std::make_unique<adaptation::HybridFloor<T> >(pm, lambda, adapt_metric);\n'''
    text = replace_once(text, selector, selector_new, "v2 strategy selector insertion")
    path.write_text(text)


def patch_main(path: Path) -> None:
    raw = path.read_bytes()
    observed = git_blob_sha1(raw)
    if observed != MAIN_BLOB:
        raise RuntimeError(f"main.cpp preimage {observed} != {MAIN_BLOB}")
    text = raw.decode()

    seed_line = "    random::seed(10);\n"
    seed_new = '''    unsigned long experiment_seed = 10;\n    if (argc >= 10)\n        experiment_seed = std::strtoul(argv[9], nullptr, 10);\n    random::seed(experiment_seed);\n'''
    text = replace_once(text, seed_line, seed_new, "optional seed plumbing")
    path.write_text(text)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("upstream_root")
    args = parser.parse_args()
    root = Path(args.upstream_root)
    patch_gsemo(root / "src" / "gsemo.hpp")
    patch_main(root / "src" / "main.cpp")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
