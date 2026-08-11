function result = eu2607_fixed_tape_generation( ...
        parent, n, k, lambda_real, update_factor, profile, ...
        mutation_children, crossover_children, ...
        mutation_tie_choice, final_tie_choice)
%EU2607_FIXED_TAPE_GENERATION Execute one selection/update policy fixture.
%
% The offspring are supplied by the caller, eliminating RNG mapping while
% preserving the audited profile differences.  Tie choices are zero-based
% indices into the ordered best-candidate multiset, matching canonical.py.

if nargin < 9
    mutation_tie_choice = 0;
end
if nargin < 10
    final_tie_choice = 0;
end
profile = require_profile(profile);
[~, ~] = eu2607_jump_fitness(parent, n, k);
offspring_count = eu2607_round_lambda(lambda_real, profile.name);
mutants = require_tape(mutation_children, offspring_count, n, k);
crossovers = require_tape(crossover_children, offspring_count, n, k);

selected_mutant = best_by_fitness( ...
    mutants, n, k, mutation_tie_choice);
switch profile.final_pool
    case 'selected_best_mutant_plus_crossover_children'
        raw_pool = [selected_mutant, crossovers];
    case 'all_mutants_plus_crossover_children'
        raw_pool = [mutants, crossovers];
    otherwise
        error('EU2607:BadProfile', 'Unsupported final-pool policy');
end
final_pool = raw_pool(raw_pool ~= parent);

[old_fitness, ~] = eu2607_jump_fitness(parent, n, k);
if isempty(final_pool)
    selected_candidate = parent;
else
    selected_candidate = best_by_fitness( ...
        final_pool, n, k, final_tie_choice);
end
[selected_fitness, ~] = eu2607_jump_fitness(selected_candidate, n, k);
strict_success = selected_fitness > old_fitness;
if selected_fitness >= old_fitness
    parent_after = selected_candidate;
else
    parent_after = parent;
end
lambda_after = eu2607_update_lambda( ...
    lambda_real, strict_success, update_factor, double(n), true);

result = struct();
result.profile = profile.name;
result.parent_before = double(parent);
result.parent_after = double(parent_after);
result.selected_mutant = double(selected_mutant);
result.selected_candidate = double(selected_candidate);
result.strict_success = strict_success;
result.lambda_before = double(lambda_real);
result.lambda_after = lambda_after;
result.logical_evaluations = 2 * offspring_count;
result.final_pool = double(final_pool);
end

function profile = require_profile(name)
if ischar(name) && isrow(name)
    % Already a character row vector.
elseif has_isstring() && isstring(name) && isscalar(name)
    name = char(name);
else
    error('EU2607:BadProfile', 'profile must be a scalar name');
end
switch name
    case 'paper_algorithm3'
        profile = struct( ...
            'name', name, ...
            'rounding', 'nearest_half_up', ...
            'final_pool', ...
                'selected_best_mutant_plus_crossover_children', ...
            'jump_shortcuts', false);
    case 'artifact_generic'
        profile = struct( ...
            'name', name, ...
            'rounding', 'python_ties_to_even', ...
            'final_pool', 'all_mutants_plus_crossover_children', ...
            'jump_shortcuts', false);
    case 'artifact_jump_optimized'
        profile = struct( ...
            'name', name, ...
            'rounding', 'python_ties_to_even', ...
            'final_pool', 'all_mutants_plus_crossover_children', ...
            'jump_shortcuts', true);
    otherwise
        error('EU2607:BadProfile', 'Unknown EU26-07 profile: %s', name);
end
end

function values = require_tape(values, expected_count, n, k)
if ~isnumeric(values) || islogical(values) || ~isreal(values) ...
        || ~isvector(values) || numel(values) ~= expected_count
    error('EU2607:BadTape', ...
        'Each tape must be a real numeric vector with exactly m entries');
end
values = reshape(values, 1, []);
for value_index = 1:numel(values)
    value = values(value_index);
    if ~isfinite(double(value)) || double(value) ~= fix(double(value))
        error('EU2607:BadTape', ...
            'Tape entries must be finite encoded bit-string integers');
    end
    try
        eu2607_jump_fitness(value, n, k);
    catch exception
        if strcmp(exception.identifier, 'EU2607:BadBitString')
            error('EU2607:BadTape', ...
                'A tape entry lies outside the n-bit domain');
        end
        rethrow(exception);
    end
end
values = double(values);
end

function selected = best_by_fitness(candidates, n, k, tie_choice)
if isempty(candidates)
    error('EU2607:BadTape', 'The candidate set must not be empty');
end
if ~is_scalar_integer(tie_choice) || tie_choice < 0
    error('EU2607:BadTieChoice', ...
        'A tie choice must be a non-negative integer');
end
fitness = zeros(1, numel(candidates));
for candidate_index = 1:numel(candidates)
    fitness(candidate_index) = eu2607_jump_fitness( ...
        candidates(candidate_index), n, k);
end
best_indices = find(fitness == max(fitness));
matlab_choice = double(tie_choice) + 1;
if matlab_choice > numel(best_indices)
    error('EU2607:BadTieChoice', ...
        'A tie choice lies outside the ordered best-candidate set');
end
selected = candidates(best_indices(matlab_choice));
end

function tf = has_isstring()
tf = exist('isstring', 'builtin') ~= 0 || exist('isstring', 'file') ~= 0;
end

function tf = is_scalar_integer(value)
tf = isnumeric(value) && ~islogical(value) && isreal(value) ...
    && isscalar(value) && isfinite(double(value)) ...
    && double(value) == fix(double(value));
end
