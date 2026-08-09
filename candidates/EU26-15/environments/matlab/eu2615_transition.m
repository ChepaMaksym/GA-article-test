function result = eu2615_transition(action, varargin)
%EU2615_TRANSITION Independent MATLAB/Octave GARBO fuzzy transition.
% This is a deterministic formula verifier only. It does not execute GARBO.

  action = lower(char(action));
  switch action
    case 'transition'
      require_arguments(action, varargin, 4);
      result = transition_from_statistics(varargin{1}, varargin{2}, ...
        varargin{3}, varargin{4});
    case 'population'
      require_arguments(action, varargin, 3);
      [statistics, transition] = transition_from_population(varargin{1}, ...
        varargin{2}, varargin{3});
      result = struct('statistics', statistics, 'transition', transition);
    case 'feature_rank'
      require_arguments(action, varargin, 2);
      result = feature_rank_delta(varargin{1}, varargin{2});
    case 'universe'
      require_arguments(action, varargin, 1);
      result = source_universe(char(varargin{1}));
    case 'memberships'
      require_arguments(action, varargin, 2);
      result = membership_degrees(char(varargin{1}), varargin{2});
    otherwise
      error('EU2615:Action', 'Unknown verifier action: %s', action);
  end
end


function require_arguments(action, values, expected)
  if numel(values) ~= expected
    error('EU2615:Arguments', '%s expects %d arguments', action, expected);
  end
end


function result = transition_from_statistics(fv, ft, mlc, ssc)
  values = double([fv, ft, mlc, ssc]);
  if ~all(isfinite(values))
    error('EU2615:Nonfinite', 'Transition statistics must be finite');
  end
  fv = values(1);
  ft = values(2);
  mlc = values(3);
  ssc = values(4);
  if ssc > 0.75
    result = struct('branch', 'similarity_override', 'cxpb', 0.0, ...
      'mutpb', 1.0, 'mutop', [0.9, 0.1, 0.0]);
    return;
  end
  result = struct('branch', 'fuzzy', ...
    'cxpb', crossover_probability(fv, mlc), ...
    'mutpb', mutation_probability(ft, mlc), ...
    'mutop', mutation_operator_probabilities(ssc, mlc));
end


function value = crossover_probability(fv, mlc)
  rows = {'high', 'med', 'low'};
  columns = {'high', 'med', 'low'};
  terms = {
    'high',    'med_high', 'med_high';
    'med',     'med',      'med_low';
    'med_low', 'low',      'low'
  };
  value = infer_rules(membership_degrees('fv', fv), ...
    membership_degrees('mlc', mlc), 'cr', rows, columns, terms);
end


function value = mutation_probability(ft, mlc)
  rows = {'high', 'med', 'low'};
  columns = {'high', 'med', 'low'};
  terms = {
    'med', 'med_high', 'high';
    'med_low', 'med', 'med_high';
    'low', 'med_low', 'med'
  };
  % Source-faithful quirk: mutationFLRules calls intFV(ft), not intFT(ft).
  value = infer_rules(membership_degrees('mlc', mlc), ...
    membership_degrees('fv', ft), 'mr', rows, columns, terms);
end


function value = insertion_probability(ssc, mlc)
  rows = {'high', 'med', 'low'};
  columns = {'low', 'med', 'high'};
  terms = {
    'high', 'med', 'med_low';
    'med_high', 'med_low', 'low';
    'med_low', 'low', 'low'
  };
  value = infer_rules(membership_degrees('ssc', ssc), ...
    membership_degrees('mlc', mlc), 'pi', rows, columns, terms);
end


function value = deletion_probability(ssc, mlc)
  rows = {'high', 'med', 'low'};
  columns = {'low', 'med', 'high'};
  terms = {
    'med_low', 'med', 'high';
    'low', 'med_low', 'med_high';
    'low', 'low', 'med_low'
  };
  value = infer_rules(membership_degrees('ssc', ssc), ...
    membership_degrees('mlc', mlc), 'pd', rows, columns, terms);
end


function probabilities = mutation_operator_probabilities(ssc, mlc)
  deletion = deletion_probability(ssc, mlc);
  insertion = insertion_probability(ssc, mlc);
  substitution = 1.0 - (deletion + insertion);
  probabilities = [insertion, deletion, substitution];
end


function value = feature_rank_delta(usage, benefit)
  rows = {'high', 'med', 'low'};
  columns = {'low', 'med', 'high'};
  terms = {
    'low', 'med', 'med_high';
    'med_low', 'med_high', 'high';
    'med_low', 'med', 'med_high'
  };
  value = infer_rules(membership_degrees('eva', usage), ...
    membership_degrees('eva', benefit), 'est', rows, columns, terms);
end


function value = infer_rules(row_degrees, column_degrees, output_name, ...
    row_names, column_names, terms)
  universe = source_universe(output_name);
  aggregated = zeros(size(universe));
  for row_index = 1:numel(row_names)
    for column_index = 1:numel(column_names)
      activation = min(row_degrees.(row_names{row_index}), ...
        column_degrees.(column_names{column_index}));
      consequent = sampled_membership(output_name, ...
        terms{row_index, column_index});
      aggregated = max(aggregated, min(activation, consequent));
    end
  end
  value = piecewise_centroid(universe, aggregated);
end


function degrees = membership_degrees(variable, value)
  value = double(value);
  if ~isscalar(value) || ~isfinite(value)
    error('EU2615:MembershipInput', 'Membership input must be finite scalar');
  end
  [terms, ~, ~] = membership_spec(variable);
  universe = source_universe(variable);
  degrees = struct();
  for index = 1:numel(terms)
    sampled = sampled_membership(variable, terms{index});
    degrees.(terms{index}) = interp_zero_outside(universe, sampled, value);
  end
end


function sampled = sampled_membership(variable, requested_term)
  [terms, shapes, parameters] = membership_spec(variable);
  index = find(strcmp(terms, requested_term), 1, 'first');
  if isempty(index)
    error('EU2615:MembershipTerm', 'Unknown %s term: %s', ...
      variable, requested_term);
  end
  universe = source_universe(variable);
  if strcmp(shapes{index}, 'tri')
    sampled = triangular_samples(universe, parameters{index});
  elseif strcmp(shapes{index}, 'trap')
    sampled = trapezoidal_samples(universe, parameters{index});
  else
    error('EU2615:MembershipShape', 'Unknown membership shape');
  end
end


function [terms, shapes, parameters] = membership_spec(variable)
  switch char(variable)
    case 'fv'
      terms = {'low', 'med', 'high'};
      shapes = {'trap', 'tri', 'trap'};
      parameters = {[-0.01, -0.01, 0.0, 0.03], ...
        [0.02, 0.05, 0.08], [0.07, 0.1, 0.4, 0.7]};
    case 'ft'
      terms = {'low', 'med', 'high'};
      shapes = {'trap', 'tri', 'trap'};
      parameters = {[-0.01, -0.01, 0.005, 0.01], ...
        [0.0075, 0.015, 0.03], [0.02, 0.04, 0.4, 0.7]};
    case 'mlc'
      terms = {'low', 'med', 'high'};
      shapes = {'trap', 'tri', 'trap'};
      parameters = {[0.0, 0.0, 5.0, 15.0], ...
        [10.0, 20.0, 30.0], [25.0, 35.0, 200.0, 200.0]};
    case 'ssc'
      terms = {'low', 'med', 'high'};
      shapes = {'trap', 'tri', 'trap'};
      parameters = {[-0.01, -0.01, 0.0, 0.2], ...
        [0.1, 0.3, 0.5], [0.4, 0.6, 1.01, 1.01]};
    case 'eva'
      terms = {'low', 'med', 'high'};
      shapes = {'trap', 'tri', 'trap'};
      parameters = {[0.0, 0.0, 0.1, 0.4], ...
        [0.2, 0.5, 0.8], [0.6, 0.9, 1.1, 1.1]};
    case 'cr'
      terms = {'low', 'med_low', 'med', 'med_high', 'high'};
      shapes = {'trap', 'tri', 'tri', 'tri', 'trap'};
      parameters = {[0.0, 0.0, 0.1, 0.2], [0.15, 0.25, 0.35], ...
        [0.3, 0.4, 0.5], [0.45, 0.55, 0.65], ...
        [0.6, 0.7, 0.8, 0.8]};
    case 'mr'
      terms = {'low', 'med_low', 'med', 'med_high', 'high'};
      shapes = {'trap', 'tri', 'tri', 'tri', 'trap'};
      parameters = {[0.0, 0.0, 0.05, 0.08], [0.07, 0.1, 0.13], ...
        [0.12, 0.15, 0.18], [0.17, 0.2, 0.23], ...
        [0.22, 0.25, 0.3, 0.3]};
    case {'pi', 'pd'}
      terms = {'low', 'med_low', 'med', 'med_high', 'high'};
      shapes = {'trap', 'tri', 'tri', 'tri', 'trap'};
      parameters = {[0.1, 0.1, 0.1, 0.15], [0.125, 0.175, 0.225], ...
        [0.2, 0.25, 0.3], [0.275, 0.325, 0.375], ...
        [0.35, 0.4, 0.4, 0.4]};
    case 'est'
      terms = {'low', 'med_low', 'med', 'med_high', 'high'};
      shapes = {'trap', 'tri', 'tri', 'tri', 'trap'};
      parameters = {[-0.12, -0.12, -0.1, -0.07], ...
        [-0.08, -0.05, -0.02], [-0.03, 0.0, 0.03], ...
        [0.02, 0.05, 0.08], [0.07, 0.1, 0.12, 0.12]};
    otherwise
      error('EU2615:MembershipVariable', ...
        'No membership specification for %s', variable);
  end
end


function values = source_universe(name)
  switch char(name)
    case {'fv', 'ft'}
      values = source_arange(-0.01, 0.7, 0.001);
    case 'mlc'
      values = source_arange(0.0, 200.0, 1.0);
    case 'ssc'
      values = source_arange(-0.01, 1.01, 0.01);
    case 'eva'
      values = source_arange(0.0, 1.1, 0.01);
    case 'cr'
      values = source_arange(0.0, 0.8, 0.01);
    case 'mr'
      values = source_arange(0.0, 0.3, 0.01);
    case {'pi', 'pd'}
      values = source_arange(0.1, 0.4, 0.01);
    case 'pl'
      values = source_arange(0.0, 0.6, 0.01);
    case 'est'
      values = source_arange(-0.12, 0.12, 0.01);
    otherwise
      error('EU2615:Universe', 'Unknown universe: %s', name);
  end
end


function values = source_arange(start_value, stop_value, step)
  count = ceil((stop_value - start_value) / step);
  effective_step = (start_value + step) - start_value;
  values = start_value + (0:(count - 1)) * effective_step;
end


function values = triangular_samples(x, parameters)
  a = parameters(1);
  b = parameters(2);
  c = parameters(3);
  if ~(a <= b && b <= c)
    error('EU2615:Triangle', 'Invalid triangular parameters');
  end
  values = zeros(size(x));
  if a ~= b
    indices = (a < x) & (x < b);
    values(indices) = (x(indices) - a) / (b - a);
  end
  if b ~= c
    indices = (b < x) & (x < c);
    values(indices) = (c - x(indices)) / (c - b);
  end
  values(x == b) = 1.0;
end


function values = trapezoidal_samples(x, parameters)
  a = parameters(1);
  b = parameters(2);
  c = parameters(3);
  d = parameters(4);
  if ~(a <= b && b <= c && c <= d)
    error('EU2615:Trapezoid', 'Invalid trapezoidal parameters');
  end
  values = ones(size(x));
  indices = x <= b;
  values(indices) = triangular_samples(x(indices), [a, b, b]);
  indices = x >= c;
  values(indices) = triangular_samples(x(indices), [c, c, d]);
  values(x < a) = 0.0;
  values(x > d) = 0.0;
end


function result = interp_zero_outside(x, membership, value)
  if value < x(1) || value > x(end)
    result = 0.0;
    return;
  end
  exact = find(x == value, 1, 'first');
  if ~isempty(exact)
    result = membership(exact);
    return;
  end
  upper = find(x > value, 1, 'first');
  if isempty(upper) || upper == 1
    result = 0.0;
    return;
  end
  lower_index = upper - 1;
  result = membership(lower_index) + ...
    (value - x(lower_index)) * ...
    (membership(upper) - membership(lower_index)) / ...
    (x(upper) - x(lower_index));
end


function result = piecewise_centroid(x, membership)
  if numel(x) ~= numel(membership) || isempty(x)
    error('EU2615:CentroidShape', 'Centroid arrays must align');
  end
  if sum(membership) == 0.0
    error('EU2615:ZeroArea', 'Total area is zero in defuzzification');
  end
  sum_moment_area = 0.0;
  sum_area = 0.0;
  for index = 2:numel(x)
    x1 = x(index - 1);
    x2 = x(index);
    y1 = membership(index - 1);
    y2 = membership(index);
    if (y1 == 0.0 && y2 == 0.0) || x1 == x2
      continue;
    end
    if y1 == y2
      moment = 0.5 * (x1 + x2);
      area = (x2 - x1) * y1;
    elseif y1 == 0.0
      moment = (2.0 / 3.0) * (x2 - x1) + x1;
      area = 0.5 * (x2 - x1) * y2;
    elseif y2 == 0.0
      moment = (1.0 / 3.0) * (x2 - x1) + x1;
      area = 0.5 * (x2 - x1) * y1;
    else
      moment = ((2.0 / 3.0) * (x2 - x1) * ...
        (y2 + 0.5 * y1)) / (y1 + y2) + x1;
      area = 0.5 * (x2 - x1) * (y1 + y2);
    end
    sum_moment_area = sum_moment_area + moment * area;
    sum_area = sum_area + area;
  end
  if sum_area == 0.0
    error('EU2615:ZeroArea', 'Piecewise centroid area is zero');
  end
  result = sum_moment_area / sum_area;
end


function [statistics, transition] = transition_from_population(fitness, ...
    previous_mean_fitness, chromosomes)
  fitness = double(fitness(:)');
  previous_mean_fitness = double(previous_mean_fitness);
  if isempty(fitness) || ~isscalar(previous_mean_fitness) || ...
      ~isfinite(previous_mean_fitness) || ~all(isfinite(fitness))
    error('EU2615:Fitness', 'Fitness and previous mean must be finite');
  end
  chromosome_values = normalize_chromosomes(chromosomes);
  if numel(fitness) ~= numel(chromosome_values)
    error('EU2615:PopulationCount', ...
      'Fitness and chromosome counts must match');
  end
  if numel(chromosome_values) < 2
    error('EU2615:PopulationPairs', 'SSC requires at least two chromosomes');
  end
  lengths = zeros(1, numel(chromosome_values));
  for index = 1:numel(chromosome_values)
    chromosome = chromosome_values{index}(:)';
    if numel(unique(chromosome)) ~= numel(chromosome)
      error('EU2615:DuplicateGene', ...
        'Chromosomes must have source set semantics');
    end
    chromosome_values{index} = chromosome;
    lengths(index) = numel(chromosome);
  end
  maximum = max(fitness);
  if maximum == 0.0
    error('EU2615:ZeroMaximum', ...
      'FV is undefined when maximum fitness is zero');
  end
  mean_fitness = sum(fitness) / numel(fitness);
  fv = (maximum - mean_fitness) / maximum;
  ft = abs(mean_fitness - previous_mean_fitness);
  mlc = sum(lengths) / numel(lengths);

  similarity_sum = 0.0;
  comparisons = 0;
  for left_index = 1:numel(chromosome_values)
    for right_index = 1:(left_index - 1)
      left = chromosome_values{left_index};
      right = chromosome_values{right_index};
      combined = union(left, right);
      if isempty(combined)
        error('EU2615:EmptyUnion', ...
          'Jaccard similarity is undefined for empty union');
      end
      similarity_sum = similarity_sum + ...
        numel(intersect(left, right)) / numel(combined);
      comparisons = comparisons + 1;
    end
  end
  if comparisons == 0
    error('EU2615:PopulationPairs', 'SSC requires at least one pair');
  end
  ssc = similarity_sum / comparisons;
  statistics = struct('fv', fv, 'ft', ft, 'mlc', mlc, 'ssc', ssc, ...
    'mean_fitness', mean_fitness);
  transition = transition_from_statistics(fv, ft, mlc, ssc);
end


function values = normalize_chromosomes(chromosomes)
  if iscell(chromosomes)
    values = chromosomes(:)';
  elseif isnumeric(chromosomes)
    values = cell(1, size(chromosomes, 1));
    for index = 1:size(chromosomes, 1)
      values{index} = chromosomes(index, :);
    end
  else
    error('EU2615:ChromosomeType', 'Unsupported chromosome container');
  end
end
