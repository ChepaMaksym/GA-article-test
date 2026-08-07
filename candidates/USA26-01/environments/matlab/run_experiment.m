function summary = run_experiment(function_name, dimension, initial_std, seed, generations)
%RUN_EXPERIMENT Run one frozen-matrix configuration or a diagnostic budget.

generation_map = [2, 100; 30, 300; 100, 1000; 1000, 2500];
row = find(generation_map(:, 1) == dimension, 1);
if isempty(row)
    error('gesmr:UnregisteredDimension', ...
        'dimension must be one of 2, 30, 100, or 1000');
end
if ~(initial_std == 1 || initial_std == 10)
    error('gesmr:UnregisteredInitialStd', 'initial_std must be 1 or 10');
end
if seed < 0 || seed > 39 || seed ~= round(seed)
    error('gesmr:UnregisteredSeed', 'seed must be an integer from 0 through 39');
end
source_generations = generation_map(row, 2);
if nargin < 5 || isempty(generations)
    generations = source_generations;
end

result = run_gesmr(function_name, dimension, initial_std, seed, generations);
summary = struct();
summary.candidate_id = 'USA26-01';
summary.algorithm = 'GESMR';
summary.task_class = 'direct_analytic_minimization';
summary.function_name = char(function_name);
summary.dimension = dimension;
summary.initial_std = initial_std;
summary.seed = seed;
summary.generations = generations;
summary.source_grounded_generations = source_generations;
summary.diagnostic_budget_override = generations ~= source_generations;
summary.objective_call_count = result.objective_call_count;
summary.objective_row_evaluation_count = result.objective_row_evaluation_count;
summary.initial_best = result.best_fitness_history(1);
summary.final_best = result.best_fitness_history(end);
summary.initial_geometric_mean_sigma = result.geometric_mean_sigma_history(1);
summary.final_geometric_mean_sigma = result.geometric_mean_sigma_history(end);
summary.initial_arithmetic_mean_sigma_diagnostic = ...
    result.arithmetic_mean_sigma_history(1);
summary.final_arithmetic_mean_sigma_diagnostic = ...
    result.arithmetic_mean_sigma_history(end);
summary.mutation_rates_changed_within_run = any(any( ...
    result.sigma_history(2:end, :) ~= result.sigma_history(1:end-1, :)));
summary.verification_status = 'NOT_A_PUBLISHED_RESULT_GATE';
end
