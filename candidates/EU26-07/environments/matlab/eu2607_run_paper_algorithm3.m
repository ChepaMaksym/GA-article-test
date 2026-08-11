function result = eu2607_run_paper_algorithm3(config)
%EU2607_RUN_PAPER_ALGORITHM3 Run the paper-faithful resetting (1+(lambda,lambda)) GA.
%
% This is an independent MATLAB/GNU Octave implementation of Algorithm 3
% from Hevia Fajardo and Sudholt. It intentionally uses the paper profile:
%   - lambda is rounded to the nearest integer with exact halves upward;
%   - one L ~ Bin(n,lambda/n) is shared by all mutation offspring;
%   - every mutant flips exactly L distinct uniformly selected positions;
%   - final selection uses the selected best mutant plus crossover offspring;
%   - strict success is evaluated against the pre-replacement parent;
%   - an unsuccessful generation at lambda=n resets lambda to one.
%
% The last point repairs the printed line-order ambiguity in Algorithm 3:
% line 12 replaces x before line 13 compares f(y)>f(x). The surrounding
% analysis defines success as leaving the current fitness level, so this
% runner retains the old parent fitness for the success comparison.
%
% CONFIG is a scalar struct. Supported fields:
%   n                 integer >= 11                     (default 20)
%   k                 integer in [1,n)                  (default 4)
%   update_factor     finite F > 1                      (default 1.5)
%   seed              non-negative integer              (default 1)
%   max_generations   positive integer or Inf           (default Inf)
%   max_evaluations   non-negative integer or Inf       (default Inf)
%   initial_parent    optional 1-by-n zero-one row       (default random)
%   record_trace      logical scalar                     (default false)
%
% Logical evaluations follow the pseudocode and count all m mutation and m
% crossover offspring in a completed generation. The initial parent is not
% charged because Algorithm 3 samples it without an explicit query line.

if nargin < 1
    config = struct();
end
config = normalize_config(config);
rng(double(config.seed), 'twister');

if isempty(config.initial_parent)
    parent = rand(1, config.n) < 0.5;
else
    parent = require_bit_row(config.initial_parent, config.n, 'initial_parent');
end
[parent_fitness, parent_solved] = eu2607_jump_fitness_bits( ...
    parent, config.n, config.k);
parent_fitness = double(parent_fitness);
parent_solved = logical(parent_solved);

lambda_real = 1.0;
generations = 0;
logical_evaluations = 0;
last_controls = eu2607_controls( ...
    lambda_real, config.n, 'paper_algorithm3', 1.0);
trace = empty_trace();
status = 'RUNNING';

while true
    if parent_solved
        if generations == 0
            status = 'SOLVED_INITIAL_PARENT';
        else
            status = 'SOLVED';
        end
        break;
    end
    if generations >= config.max_generations
        status = 'MAX_GENERATIONS';
        break;
    end

    controls = eu2607_controls( ...
        lambda_real, config.n, 'paper_algorithm3', 1.0);
    generation_cost = 2 * controls.offspring_count;
    if logical_evaluations + generation_cost > config.max_evaluations
        status = 'MAX_EVALUATIONS';
        break;
    end

    old_parent = parent;
    old_fitness = parent_fitness;
    ell = sum(rand(1, config.n) < controls.mutation_probability);

    mutants = repmat(old_parent, controls.offspring_count, 1);
    for offspring_index = 1:controls.offspring_count
        if ell > 0
            positions = randperm(config.n, ell);
            mutants(offspring_index, positions) = ...
                ~mutants(offspring_index, positions);
        end
    end
    [mutant_fitness, ~] = eu2607_jump_fitness_bits( ...
        mutants, config.n, config.k);
    [selected_mutant, selected_mutant_fitness] = choose_best_uniform( ...
        mutants, mutant_fitness);

    crossovers = repmat(old_parent, controls.offspring_count, 1);
    mutant_matrix = repmat(selected_mutant, controls.offspring_count, 1);
    crossover_mask = rand(controls.offspring_count, config.n) ...
        < controls.crossover_probability;
    crossovers(crossover_mask) = mutant_matrix(crossover_mask);
    [crossover_fitness, ~] = eu2607_jump_fitness_bits( ...
        crossovers, config.n, config.k);

    raw_pool = [selected_mutant; crossovers];
    raw_fitness = [selected_mutant_fitness; crossover_fitness];
    differs_from_parent = any(raw_pool ~= repmat( ...
        old_parent, size(raw_pool, 1), 1), 2);
    if any(differs_from_parent)
        [candidate, candidate_fitness] = choose_best_uniform( ...
            raw_pool(differs_from_parent, :), ...
            raw_fitness(differs_from_parent));
    else
        candidate = old_parent;
        candidate_fitness = old_fitness;
    end

    strict_success = candidate_fitness > old_fitness;
    accepted = candidate_fitness >= old_fitness;
    if accepted
        parent = candidate;
        parent_fitness = double(candidate_fitness);
    else
        parent = old_parent;
        parent_fitness = old_fitness;
    end
    parent_solved = parent_fitness == double(config.n + config.k);

    lambda_after = eu2607_update_lambda( ...
        lambda_real, strict_success, config.update_factor, ...
        double(config.n), true);
    generations = generations + 1;
    logical_evaluations = logical_evaluations + generation_cost;
    last_controls = controls;

    if config.record_trace
        trace = append_trace(trace, generations, old_fitness, ...
            parent_fitness, lambda_real, lambda_after, controls, ell, ...
            strict_success, accepted, generation_cost, sum(parent));
    end
    lambda_real = lambda_after;
end

result = struct();
result.schema_version = 1;
result.profile = 'paper_algorithm3_fixed_order';
result.paper_algorithm = 'Algorithm 3 resetting lambda';
result.status = status;
result.solved = parent_solved;
result.n = config.n;
result.k = config.k;
result.update_factor = config.update_factor;
result.lambda_max = config.n;
result.seed = config.seed;
result.generations = generations;
result.logical_evaluations = logical_evaluations;
result.initial_parent_charged = false;
result.final_parent = parent;
result.final_fitness = parent_fitness;
result.final_ones = sum(parent);
result.lambda_final = lambda_real;
result.last_offspring_count = last_controls.offspring_count;
result.last_mutation_probability = last_controls.mutation_probability;
result.last_crossover_probability = last_controls.crossover_probability;
result.trace = trace;
result.semantics = struct( ...
    'rounding', 'nearest_half_up', ...
    'mutation_strength_draws_per_generation', 1, ...
    'mutation_positions', 'exact_distinct_uniform', ...
    'final_pool', 'selected_best_mutant_plus_crossovers_excluding_parent', ...
    'success_reference', 'pre_replacement_parent', ...
    'reset_condition', 'unsuccessful_generation_at_lambda_equal_n', ...
    'evaluation_accounting', 'two_times_rounded_lambda_per_completed_generation');
result.claim_boundary = [ ...
    'Independent paper-profile implementation; it is not the author ', ...
    'artifact profile and does not by itself reproduce a published figure.'];
end

function config = normalize_config(config)
if ~isstruct(config) || ~isscalar(config)
    error('EU2607:BadConfig', 'config must be a scalar struct');
end
config.n = field_or_default(config, 'n', 20);
config.k = field_or_default(config, 'k', 4);
config.update_factor = field_or_default(config, 'update_factor', 1.5);
config.seed = field_or_default(config, 'seed', 1);
config.max_generations = field_or_default(config, 'max_generations', Inf);
config.max_evaluations = field_or_default(config, 'max_evaluations', Inf);
config.initial_parent = field_or_default(config, 'initial_parent', []);
config.record_trace = field_or_default(config, 'record_trace', false);

if ~is_scalar_integer(config.n) || config.n < 11
    error('EU2607:BadProblem', 'n must be an integer >= 11');
end
if ~is_scalar_integer(config.k) || config.k < 1 || config.k >= config.n
    error('EU2607:BadProblem', 'k must be an integer in [1,n)');
end
if ~is_scalar_real(config.update_factor) || config.update_factor <= 1
    error('EU2607:BadUpdateFactor', 'update_factor must be finite and > 1');
end
if ~is_scalar_integer(config.seed) || config.seed < 0
    error('EU2607:BadSeed', 'seed must be a non-negative integer');
end
validate_limit(config.max_generations, 'max_generations', false);
validate_limit(config.max_evaluations, 'max_evaluations', true);
if ~islogical(config.record_trace) || ~isscalar(config.record_trace)
    error('EU2607:BadConfig', 'record_trace must be a logical scalar');
end
if ~isempty(config.initial_parent)
    config.initial_parent = require_bit_row( ...
        config.initial_parent, config.n, 'initial_parent');
end
config.n = double(config.n);
config.k = double(config.k);
config.update_factor = double(config.update_factor);
config.seed = double(config.seed);
config.max_generations = double(config.max_generations);
config.max_evaluations = double(config.max_evaluations);
end

function value = field_or_default(config, name, default_value)
if isfield(config, name)
    value = config.(name);
else
    value = default_value;
end
end

function validate_limit(value, name, allow_zero)
if isnumeric(value) && ~islogical(value) && isreal(value) && isscalar(value) ...
        && isinf(double(value)) && double(value) > 0
    return;
end
minimum = 1;
if allow_zero
    minimum = 0;
end
if ~is_scalar_integer(value) || value < minimum
    error('EU2607:BadConfig', ...
        '%s must be an integer >= %d or positive Inf', name, minimum);
end
end

function row = require_bit_row(value, n, label)
if islogical(value)
    row = value;
elseif isnumeric(value) && isreal(value) && all(isfinite(double(value(:)))) ...
        && all(double(value(:)) == 0 | double(value(:)) == 1)
    row = logical(value);
else
    error('EU2607:BadBitMatrix', '%s must contain only zero-one values', label);
end
if ~isvector(row) || numel(row) ~= double(n)
    error('EU2607:BadBitMatrix', '%s must be a vector with n entries', label);
end
row = reshape(row, 1, []);
end

function [selected, selected_fitness] = choose_best_uniform(candidates, fitness)
if isempty(candidates) || size(candidates, 1) ~= numel(fitness)
    error('EU2607:InternalSelection', 'candidate/fitness sizes do not agree');
end
fitness = reshape(double(fitness), [], 1);
best_indices = find(fitness == max(fitness));
chosen_index = best_indices(randi(numel(best_indices)));
selected = candidates(chosen_index, :);
selected_fitness = fitness(chosen_index);
end

function trace = empty_trace()
trace = struct();
trace.generation = zeros(0, 1);
trace.parent_fitness_before = zeros(0, 1);
trace.parent_fitness_after = zeros(0, 1);
trace.lambda_before = zeros(0, 1);
trace.lambda_after = zeros(0, 1);
trace.offspring_count = zeros(0, 1);
trace.mutation_probability = zeros(0, 1);
trace.crossover_probability = zeros(0, 1);
trace.mutation_strength = zeros(0, 1);
trace.strict_success = false(0, 1);
trace.accepted = false(0, 1);
trace.logical_evaluation_increment = zeros(0, 1);
trace.parent_ones_after = zeros(0, 1);
end

function trace = append_trace(trace, generation, fitness_before, fitness_after, ...
        lambda_before, lambda_after, controls, ell, strict_success, accepted, ...
        evaluation_increment, parent_ones_after)
row = numel(trace.generation) + 1;
trace.generation(row, 1) = generation;
trace.parent_fitness_before(row, 1) = fitness_before;
trace.parent_fitness_after(row, 1) = fitness_after;
trace.lambda_before(row, 1) = lambda_before;
trace.lambda_after(row, 1) = lambda_after;
trace.offspring_count(row, 1) = controls.offspring_count;
trace.mutation_probability(row, 1) = controls.mutation_probability;
trace.crossover_probability(row, 1) = controls.crossover_probability;
trace.mutation_strength(row, 1) = ell;
trace.strict_success(row, 1) = strict_success;
trace.accepted(row, 1) = accepted;
trace.logical_evaluation_increment(row, 1) = evaluation_increment;
trace.parent_ones_after(row, 1) = parent_ones_after;
end

function tf = is_scalar_integer(value)
tf = isnumeric(value) && ~islogical(value) && isreal(value) ...
    && isscalar(value) && isfinite(double(value)) ...
    && double(value) == fix(double(value));
end

function tf = is_scalar_real(value)
tf = isnumeric(value) && ~islogical(value) && isreal(value) ...
    && isscalar(value) && isfinite(double(value));
end
