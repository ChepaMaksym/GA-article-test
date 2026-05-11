# Astrand-Ferris MATLAB GA Survival Analysis

Minimal MATLAB-native project for the local PDF:

- `article/AstrandFerris_BachelorThesis_PostPresentation_.pdf`
- Jonatan Astrand-Ferris, "Self-Adaptive Mutation Operators for Genetic Neural Networks in Survival Analysis", 2019.

The active implementation is intentionally small: it uses MATLAB `ga` from Global Optimization Toolbox to train MLP weights on c-index error.

## Main Flow

```text
main
-> synthetic_survival_datasets
-> train_validation_split
-> optimoptions('ga')
-> ga(...)
   -> gnn_fitness
      -> mlp_predict
      -> c_index_error
-> sandbox/results/matlab_ga_report.md
```

## MATLAB GA Methods

The main flow uses built-in MATLAB methods:

- `ga`
- `optimoptions`
- `selectionstochunif`
- `crossoverscattered`
- `mutationgaussian`

## Run

```matlab
main
```

Optional smoke tests:

```matlab
addpath(genpath('src'));
addpath('tests');
run_unit_tests_impl
```

## Scope

The PDF does not bundle the original medical raw datasets or Java implementation. This project uses deterministic synthetic survival datasets with the feature/sample counts described in the PDF. Numerical results are therefore marked as synthetic reproduction.

## Dependency

MATLAB with Global Optimization Toolbox.
