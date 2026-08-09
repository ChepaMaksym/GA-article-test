function state = eu2609_controls(lambda_real, dimension, crossover_rate)
% Map real lambda under source and paper-diagnostic offspring semantics.
if nargin < 3
    crossover_rate = 1.0;
end
if ~isnumeric(lambda_real) || ~isscalar(lambda_real) || ~isfinite(lambda_real) ...
        || lambda_real <= 0
    error('EU2609:Control', 'lambda_real must be a finite positive scalar');
end
if ~isnumeric(dimension) || ~isscalar(dimension) || ~isfinite(dimension) ...
        || dimension <= 1 || dimension ~= floor(dimension)
    error('EU2609:Control', 'dimension must be an integer greater than one');
end
if lambda_real > dimension
    error('EU2609:Control', 'lambda_real exceeds the cap');
end
if ~isnumeric(crossover_rate) || ~isscalar(crossover_rate) ...
        || ~isfinite(crossover_rate) || crossover_rate <= 0
    error('EU2609:Control', 'crossover_rate must be finite and positive');
end

state = struct();
state.lambda_real = lambda_real;
state.mutation_probability = lambda_real / dimension;
if crossover_rate >= 1
    state.crossover_probability = min(1, crossover_rate / lambda_real);
else
    state.crossover_probability = crossover_rate;
end
state.source_offspring_count = eu2609_round_ties_even(lambda_real);
state.paper_offspring_count = ceil(lambda_real);
state.evaluation_increment = 2 * state.source_offspring_count;
end
