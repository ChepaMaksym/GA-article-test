function result = eu2617_transition(fitness, state, cfg)
%EU2617_TRANSITION One clean-room SupRB SAGA1 rate transition.
%
% The upstream source does not guard empty, non-finite, or zero-maximum
% fitness.  This validation harness deliberately rejects those inputs.

if nargin < 3 || isempty(cfg)
    cfg = eu2617_default_config();
end
if nargin < 2 || isempty(state)
    state = struct('mutation_rate', 0.025, 'crossover_rate', 0.75);
end
eu2617_validate_config(cfg);

if ~isnumeric(fitness) || ~isvector(fitness) || isempty(fitness)
    error('eu2617:BadFitness', 'fitness must be a nonempty numeric vector');
end
fitness = fitness(:);
if any(~isfinite(fitness))
    error('eu2617:BadFitness', 'fitness must contain only finite values');
end
fitness_max = max(fitness);
if fitness_max == 0
    error('eu2617:BadFitness', 'max(fitness) must be nonzero');
end

if ~isstruct(state) || ~isfield(state, 'mutation_rate') ...
        || ~isfield(state, 'crossover_rate')
    error('eu2617:BadState', 'state must contain both rates');
end
if ~isnumeric(state.mutation_rate) || ~isscalar(state.mutation_rate) ...
        || ~isfinite(state.mutation_rate) ...
        || state.mutation_rate < cfg.mutation_rate_min ...
        || state.mutation_rate > cfg.mutation_rate_max
    error('eu2617:BadState', 'mutation_rate is outside its configured bounds');
end
if ~isnumeric(state.crossover_rate) || ~isscalar(state.crossover_rate) ...
        || ~isfinite(state.crossover_rate) ...
        || state.crossover_rate < cfg.crossover_rate_min ...
        || state.crossover_rate > cfg.crossover_rate_max
    error('eu2617:BadState', 'crossover_rate is outside its configured bounds');
end

gdm = mean(fitness) / fitness_max;
mutation_rate = state.mutation_rate;
crossover_rate = state.crossover_rate;
branch = 'no_change';
if gdm > cfg.v_max
    mutation_rate = min( ...
        cfg.mutation_rate_max, ...
        mutation_rate * cfg.mutation_rate_multiplier);
    crossover_rate = max( ...
        cfg.crossover_rate_min, ...
        crossover_rate / cfg.crossover_rate_multiplier);
    branch = 'above_v_max';
elseif gdm < cfg.v_min
    mutation_rate = max( ...
        cfg.mutation_rate_min, ...
        mutation_rate / cfg.mutation_rate_multiplier);
    crossover_rate = min( ...
        cfg.crossover_rate_max, ...
        crossover_rate * cfg.crossover_rate_multiplier);
    branch = 'below_v_min';
end

result = struct();
result.gdm = gdm;
result.previous = state;
result.current = struct( ...
    'mutation_rate', mutation_rate, ...
    'crossover_rate', crossover_rate);
result.branch = branch;
end
