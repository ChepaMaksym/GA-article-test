function result = run_gesmr(objective, dimension, initial_std, seed, generations, cfg)
%RUN_GESMR Execute one deterministic-seed GESMR analytic run.
%
% This is a direct optimizer. It does not perform inversion, system
% identification, source reconstruction, or forward-model parameter fitting.

if nargin < 6 || isempty(cfg)
    cfg = gesmr_default_config();
end
gesmr_validate_config(cfg);
if ~isscalar(dimension) || ~isfinite(dimension) ...
        || dimension ~= round(dimension) || dimension < 1
    error('gesmr:BadDimension', 'dimension must be a positive integer');
end
if ~isscalar(initial_std) || ~isfinite(initial_std) || initial_std <= 0
    error('gesmr:BadInitialStd', 'initial_std must be finite and positive');
end
if ~isscalar(seed) || ~isfinite(seed) || seed ~= round(seed) || seed < 0
    error('gesmr:BadSeed', 'seed must be a non-negative integer');
end
if ~isscalar(generations) || ~isfinite(generations) ...
        || generations ~= round(generations) || generations < 0
    error('gesmr:BadGenerations', 'generations must be a non-negative integer');
end

rng(seed, 'twister');
population = initial_std * randn(cfg.non_elite_size + 1, dimension);
sigmas = gesmr_initial_mutation_rates(cfg);
fitness = evaluate_objective(objective, population);

best_fitness_history = zeros(generations + 1, 1);
geometric_mean_sigma_history = zeros(generations + 1, 1);
arithmetic_mean_sigma_history = zeros(generations + 1, 1);
sigma_history = zeros(generations + 1, cfg.n_groups);
best_fitness_history(1) = min(fitness);
geometric_mean_sigma_history(1) = exp(mean(log(sigmas)));
arithmetic_mean_sigma_history(1) = mean(sigmas);
sigma_history(1, :) = sigmas';

for generation = 1:generations
    step = gesmr_step(population, sigmas, objective, cfg, [], fitness);
    population = step.next_population;
    fitness = step.next_fitness;
    sigmas = step.next_sigmas;
    best_fitness_history(generation + 1) = min(fitness);
    geometric_mean_sigma_history(generation + 1) = exp(mean(log(sigmas)));
    arithmetic_mean_sigma_history(generation + 1) = mean(sigmas);
    sigma_history(generation + 1, :) = sigmas';
end

result = struct();
result.final_population = population;
result.final_fitness = fitness;
result.final_sigmas = sigmas;
result.best_fitness_history = best_fitness_history;
result.geometric_mean_sigma_history = geometric_mean_sigma_history;
result.arithmetic_mean_sigma_history = arithmetic_mean_sigma_history;
result.sigma_history = sigma_history;
result.objective_call_count = generations + 1;
result.objective_row_evaluation_count = ...
    (cfg.non_elite_size + 1) * result.objective_call_count;
result.seed = seed;
end

function values = evaluate_objective(objective, population)
if isa(objective, 'function_handle')
    values = objective(population);
else
    values = gesmr_benchmark(objective, population);
end
values = values(:);
if numel(values) ~= size(population, 1) || any(~isfinite(values))
    error('gesmr:BadObjective', 'objective must return one finite value per row');
end
end
