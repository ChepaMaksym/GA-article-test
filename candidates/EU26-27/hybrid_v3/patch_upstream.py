from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

GSEMO_BLOB = "2693144bcfccff902343a02c6c8e48d7dd263257"
MAIN_BLOB = "22025e4680da85c98e3bb5ea30db8334ca25dff3"
CAPS = (15, 20, 30, 40, 60, 100)


def git_blob_sha1(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode()
    return hashlib.sha1(header + data).hexdigest()


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one preimage, found {count}")
    return text.replace(old, new, 1)


V3_CLASS = r'''
    // EU26-27 HYBRID v3: exact TwoRate mutation adaptation plus a
    // baseline-preserving one-fifth offspring-population controller.
    template <typename SolutionType, int LambdaCap>
    struct HybridCapped : TwoRate<SolutionType>
    {
        using TwoRate<SolutionType>::TwoRate;

        void setup_problem(const std::shared_ptr<ioh::problem::IntegerSingleObjective> &problem,
                           const std::vector<SolutionType> &pareto_front,
                           const SolutionType &hv) override
        {
            TwoRate<SolutionType>::setup_problem(problem, pareto_front, hv);
            cap_effective = std::min(LambdaCap, this->n);
            lambda_real = std::max(static_cast<double>(this->lambda), lambda_floor);
            lambda_real = std::min(lambda_real, static_cast<double>(cap_effective));
            this->lambda = rounded_lambda(lambda_real);
        }

        void adapt(const std::vector<SolutionType> &pareto_front,
                   const std::vector<SolutionType> &new_population) override
        {
            const auto metrics = this->population_stats(pareto_front, new_population);
            const double before = this->pareto_metric(pareto_front);
            const double best = *std::max_element(metrics.begin(), metrics.end());
            const bool strict_success = best > before;

            // Preserve the paper-era TwoRate r update, including its RNG draw.
            TwoRate<SolutionType>::adapt(pareto_front, new_population);

            if (strict_success)
                lambda_real = std::max(lambda_real / update_factor, lambda_floor);
            else
                lambda_real = std::min(
                    lambda_real * std::pow(update_factor, 0.25),
                    static_cast<double>(cap_effective));

            this->lambda = rounded_lambda(lambda_real);
            std::cout << "HYBRID_V3_CAP " << LambdaCap << " " << lambda_real << " "
                      << this->lambda << " " << strict_success << std::endl;
        }

    private:
        int rounded_lambda(const double value) const
        {
            return std::max(static_cast<int>(lambda_floor),
                            std::min(cap_effective,
                                     static_cast<int>(std::floor(value + 0.5))));
        }

        double lambda_real = 10.0;
        int cap_effective = LambdaCap;
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
    text = replace_once(text, marker, V3_CLASS + marker, "v3 class insertion")

    selector = '''        else if (name == "TwoRate")
            return std::make_unique<adaptation::TwoRate<T> >(pm, lambda, adapt_metric);
'''
    selector_new = selector
    for cap in CAPS:
        selector_new += (
            f'        else if (name == "HybridCap{cap}")\n'
            f'            return std::make_unique<adaptation::HybridCapped<T, {cap}> >(pm, lambda, adapt_metric);\n'
        )
    text = replace_once(text, selector, selector_new, "v3 strategy selector insertion")
    path.write_text(text)


def patch_main(path: Path) -> None:
    raw = path.read_bytes()
    observed = git_blob_sha1(raw)
    if observed != MAIN_BLOB:
        raise RuntimeError(f"main.cpp preimage {observed} != {MAIN_BLOB}")
    text = raw.decode()

    seed_line = "    random::seed(10);\n"
    seed_new = '''    unsigned long experiment_seed = 10;
    if (argc >= 10)
        experiment_seed = std::strtoul(argv[9], nullptr, 10);
    random::seed(experiment_seed);
'''
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
