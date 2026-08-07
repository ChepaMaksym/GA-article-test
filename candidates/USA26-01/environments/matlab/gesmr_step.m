function result = gesmr_step(population, sigmas, objective, cfg, tape, current_fitness)
%GESMR_STEP One GESMR generation following Algorithm 1 and Eqs. (2)-(7).
%
% Optional TAPE freezes all stochastic choices for cross-environment tests.
% Its parent ranks are zero-based. Optional CURRENT_FITNESS avoids a repeated
% objective evaluation when called by RUN_GESMR.

if nargin < 4 || isempty(cfg)
    cfg = gesmr_default_config();
end
if nargin < 5
    tape = [];
end
if nargin < 6
    current_fitness = [];
end
gesmr_validate_config(cfg);

expected_rows = cfg.non_elite_size + 1;
if ~isnumeric(population) || ndims(population) ~= 2 ...
        || size(population, 1) ~= expected_rows || size(population, 2) < 1
    error('gesmr:BadPopulation', ...
        'population must have N+1 rows and at least one column');
end
if any(~isfinite(population(:)))
    error('gesmr:BadPopulation', 'population must be finite');
end
sigmas = sigmas(:);
if numel(sigmas) ~= cfg.n_groups || any(~isfinite(sigmas)) || any(sigmas <= 0)
    error('gesmr:BadMutationRates', ...
        'sigmas must contain K finite positive values');
end

if isempty(current_fitness)
    current_fitness = evaluate_objective(objective, population);
else
    current_fitness = current_fitness(:);
    if numel(current_fitness) ~= expected_rows || any(~isfinite(current_fitness))
        error('gesmr:BadFitness', 'current_fitness must contain N+1 finite values');
    end
end

% Explicit original-index tie break is the cross-language stable-sort policy.
[~, solution_order] = sortrows( ...
    [current_fitness, (1:expected_rows)'], [1, 2]);
sorted_population = population(solution_order, :);
sorted_fitness = current_fitness(solution_order);

solution_parent_count = round( ...
    cfg.solution_selection_rate * cfg.non_elite_size);
mr_parent_count = round(cfg.mr_selection_rate * cfg.n_groups);
dimension = size(population, 2);

if isempty(tape)
    solution_parent_ranks = randi( ...
        solution_parent_count, cfg.non_elite_size, 1) - 1;
    solution_noise = randn(cfg.non_elite_size, dimension);
    mr_parent_ranks = randi(mr_parent_count, cfg.n_groups - 1, 1) - 1;
    mr_uniform = -1 + 2 * rand(cfg.n_groups - 1, 1);
else
    [solution_parent_ranks, solution_noise, mr_parent_ranks, mr_uniform] = ...
        validate_tape(tape, cfg, dimension, solution_parent_count, mr_parent_count);
end

parents = zeros(size(population));
parent_fitness = zeros(expected_rows, 1);
parents(1, :) = sorted_population(1, :);
parent_fitness(1) = sorted_fitness(1);
parents(2:end, :) = sorted_population(solution_parent_ranks + 1, :);
parent_fitness(2:end) = sorted_fitness(solution_parent_ranks + 1);

group_size = cfg.non_elite_size / cfg.n_groups;
group_sigmas = kron(sigmas, ones(group_size, 1));
next_population = zeros(size(population));
next_population(1, :) = parents(1, :);
next_population(2:end, :) = parents(2:end, :) + ...
    bsxfun(@times, solution_noise, group_sigmas);
next_fitness = evaluate_objective(objective, next_population);

child_delta = next_fitness(2:end) - parent_fitness(2:end);
delta_by_group = reshape(child_delta, group_size, cfg.n_groups)';
group_delta = min(delta_by_group, [], 2);

[~, mr_order] = sortrows( ...
    [group_delta, (1:cfg.n_groups)'], [1, 2]);
sorted_sigmas = sigmas(mr_order);
next_sigmas = zeros(cfg.n_groups, 1);
next_sigmas(1) = sorted_sigmas(1);
mr_parents = sorted_sigmas(mr_parent_ranks + 1);
next_sigmas(2:end) = mr_parents .* (cfg.meta_mutation_rate .^ mr_uniform);
if any(~isfinite(next_sigmas)) || any(next_sigmas <= 0)
    error('gesmr:NumericalFailure', ...
        'MR meta-mutation produced a non-positive or non-finite value');
end

result = struct();
result.next_population = next_population;
result.next_fitness = next_fitness;
result.next_sigmas = next_sigmas;
result.selected_parents = parents;
result.selected_parent_fitness = parent_fitness;
result.group_delta = group_delta;
result.solution_parent_ranks = solution_parent_ranks;
result.mr_parent_ranks = mr_parent_ranks;
result.solution_noise = solution_noise;
result.mr_uniform = mr_uniform;
end

function values = evaluate_objective(objective, population)
if isa(objective, 'function_handle')
    values = objective(population);
else
    values = gesmr_benchmark(objective, population);
end
values = values(:);
if numel(values) ~= size(population, 1)
    error('gesmr:BadObjective', 'objective must return one value per row');
end
if any(~isfinite(values))
    error('gesmr:BadObjective', 'objective returned NaN or Inf');
end
end

function [solution_parent_ranks, solution_noise, mr_parent_ranks, mr_uniform] = ...
        validate_tape(tape, cfg, dimension, solution_parent_count, mr_parent_count)
required = {'solution_parent_ranks', 'solution_noise', 'mr_parent_ranks', 'mr_uniform'};
for i = 1:numel(required)
    if ~isfield(tape, required{i})
        error('gesmr:BadTape', 'Missing random-tape field: %s', required{i});
    end
end
solution_parent_ranks = tape.solution_parent_ranks(:);
solution_noise = tape.solution_noise;
mr_parent_ranks = tape.mr_parent_ranks(:);
mr_uniform = tape.mr_uniform(:);

if numel(solution_parent_ranks) ~= cfg.non_elite_size ...
        || any(solution_parent_ranks ~= round(solution_parent_ranks)) ...
        || any(solution_parent_ranks < 0) ...
        || any(solution_parent_ranks >= solution_parent_count)
    error('gesmr:BadTape', 'Invalid solution parent ranks');
end
if ~isequal(size(solution_noise), [cfg.non_elite_size, dimension]) ...
        || any(~isfinite(solution_noise(:)))
    error('gesmr:BadTape', 'Invalid Gaussian-noise matrix');
end
if numel(mr_parent_ranks) ~= cfg.n_groups - 1 ...
        || any(mr_parent_ranks ~= round(mr_parent_ranks)) ...
        || any(mr_parent_ranks < 0) ...
        || any(mr_parent_ranks >= mr_parent_count)
    error('gesmr:BadTape', 'Invalid MR parent ranks');
end
if numel(mr_uniform) ~= cfg.n_groups - 1 ...
        || any(~isfinite(mr_uniform)) || any(abs(mr_uniform) > 1)
    error('gesmr:BadTape', 'MR mutation variates must lie in [-1, 1]');
end
end
