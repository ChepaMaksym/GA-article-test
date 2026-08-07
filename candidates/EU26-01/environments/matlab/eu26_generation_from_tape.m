function result = eu26_generation_from_tape(case_data)
%EU26_GENERATION_FROM_TAPE One source/prose 5/5 generation on explicit tape.

required = {'n', 'lambda', 'r', 'q', 'population_bits', 'children'};
for i = 1:numel(required)
    if ~isfield(case_data, required{i})
        error('EU26:Case', 'generation case is missing %s', required{i});
    end
end
n = double(case_data.n);
lambda = double(case_data.lambda);
if ~isscalar(n) || ~isfinite(n) || n <= 0 || n ~= fix(n) || ...
        ~isscalar(lambda) || ~isfinite(lambda) || lambda <= 0 || ...
        lambda ~= fix(lambda) || mod(lambda, 2) ~= 0
    error('EU26:Case', 'n and even lambda must be positive integers');
end

raw_population = case_data.population_bits;
if ischar(raw_population) || (isstring(raw_population) && isscalar(raw_population))
    raw_population = {raw_population};
elseif isstring(raw_population)
    raw_population = cellstr(raw_population);
end
if ~iscell(raw_population) || isempty(raw_population)
    error('EU26:Population', 'population_bits must decode to a non-empty cell array');
end
population_bits = cell(1, numel(raw_population));
population_points = zeros(numel(raw_population), 2);
for i = 1:numel(raw_population)
    bits = raw_population{i};
    if isstring(bits), bits = char(bits); end
    if ~ischar(bits) || numel(bits) ~= n || any(bits ~= '0' & bits ~= '1')
        error('EU26:Bits', 'every population bit string must have length n');
    end
    population_bits{i} = double(bits - '0');
    population_points(i, :) = eu26_oneminmax(population_bits{i});
end
if size(unique(population_points, 'rows'), 1) ~= size(population_points, 1)
    error('EU26:Population', 'population objective pairs must be unique');
end

children_tape = case_data.children;
if ~isstruct(children_tape) || numel(children_tape) ~= lambda
    error('EU26:Tape', 'children tape length must equal lambda');
end
r = eu26_fraction(case_data.r);
q = eu26_fraction(case_data.q);
low_rate = r / (2 * n);
high_rate = 2 * r / n;
if low_rate <= 0 || high_rate > 1
    error('EU26:Rate', 'mutation probability lies outside (0,1]');
end
rates = [repmat(low_rate, 1, lambda / 2), repmat(high_rate, 1, lambda / 2)];
parent_indices = zeros(1, lambda);
counts = zeros(1, lambda);
child_points = zeros(lambda, 2);
for i = 1:lambda
    tape = children_tape(i);
    parent_index = double(tape.parent_index);
    if ~isscalar(parent_index) || parent_index ~= fix(parent_index) || ...
            parent_index < 0 || parent_index >= numel(population_bits)
        error('EU26:Parent', 'parent index must address the pre-generation population');
    end
    draws = double(tape.binomial_draws(:).');
    if isempty(draws) || any(~isfinite(draws)) || any(draws ~= fix(draws)) || ...
            any(draws < 0) || any(draws > n) || draws(end) <= 0 || ...
            any(draws(1:end-1) ~= 0)
        error('EU26:Binomial', 'binomial tape must end at the first positive draw');
    end
    count = draws(end);
    flips = double(tape.flip_indices(:).');
    if numel(flips) ~= count || any(~isfinite(flips)) || ...
            any(flips ~= fix(flips)) || any(flips < 0) || any(flips >= n) || ...
            numel(unique(flips)) ~= numel(flips)
        error('EU26:Flip', 'flip indices must be distinct and match the positive draw');
    end
    child_bits = population_bits{parent_index + 1};
    child_bits(flips + 1) = 1 - child_bits(flips + 1);
    parent_indices(i) = parent_index;
    counts(i) = count;
    child_points(i, :) = eu26_oneminmax(child_bits);
end

adaptation = eu26_tworate_adapt(population_points, child_points, r, q, n);
final_population = sortrows(population_points, 1);
for i = 1:lambda
    final_population = eu26_pareto_insert(final_population, child_points(i, :));
end
result = struct( ...
    'n', n, ...
    'lambda', lambda, ...
    'population_points_before', sortrows(population_points, 1), ...
    'parent_indices', parent_indices, ...
    'mutation_probabilities', rates, ...
    'positive_binomial_counts', counts, ...
    'child_points', child_points, ...
    'adaptation', adaptation, ...
    'population_points_after', final_population, ...
    'hypervolume_after', eu26_hypervolume2d(final_population, [-1, -1]));
end
