function [next, event] = eu2616_transition(state, generation, currentBest, currentAverage, maxGenerations)
% Independent source-ordered scalar transition for G3P-kEMLC Alg.doControl().
validate_state(state);
validate_integer(generation, 0, 'generation');
validate_integer(maxGenerations, 1, 'maxGenerations');
if ~isscalar(currentAverage) || ~isnumeric(currentAverage) || ~isfinite(currentAverage)
    error('EU2616:Input', 'currentAverage must be a finite numeric scalar');
end

next = state;
roundedBest = eu2616_round_best_fitness(currentBest);
next.best_fitness = single(state.best_fitness);
bestImproved = roundedBest > next.best_fitness;
if bestImproved
    next.best_fitness = roundedBest;
    next.last_best_generation = generation;
end

average = single(currentAverage);
if ~isfinite(average)
    error('EU2616:Input', 'currentAverage is outside Java float range');
end
next.best_average_fitness = single(state.best_average_fitness);
step = single(0.02);
doubleStep = single(step * single(2));
guardUpper = single(single(1) - doubleStep);
changed = false;

if average > next.best_average_fitness
    branch = 'improvement';
    % This assignment precedes the source guard and remains if the guard blocks.
    next.best_average_fitness = average;
    if next.crossover_probability < double(guardUpper) && ...
            next.mutation_probability >= double(doubleStep)
        next.crossover_probability = next.crossover_probability + 0.02;
        next.mutation_probability = next.mutation_probability - 0.02;
        changed = true;
    end
else
    branch = 'non_improvement';
    if next.mutation_probability < double(guardUpper) && ...
            next.crossover_probability >= double(doubleStep)
        next.crossover_probability = next.crossover_probability - 0.02;
        next.mutation_probability = next.mutation_probability + 0.02;
        changed = true;
    end
end
validate_state(next);

stagnated = generation >= next.last_best_generation + 10 && next.best_fitness > 0;
maximumReached = generation >= maxGenerations;
if maximumReached
    reason = 'max_generations';
elseif stagnated
    reason = 'best_fitness_stagnation';
else
    reason = '';
end
event = struct();
event.rounded_current_best_fitness = roundedBest;
event.best_fitness_improved = bestImproved;
event.average_branch = branch;
event.probabilities_changed = changed;
event.should_stop = stagnated || maximumReached;
event.stop_reason = reason;
end

function validate_state(state)
required = {'crossover_probability', 'mutation_probability', ...
    'best_average_fitness', 'best_fitness', 'last_best_generation'};
if ~isstruct(state) || ~all(isfield(state, required))
    error('EU2616:Input', 'state is missing required fields');
end
probabilities = [state.crossover_probability, state.mutation_probability];
if ~isnumeric(probabilities) || numel(probabilities) ~= 2 || ...
        any(~isfinite(probabilities)) || any(probabilities < 0) || any(probabilities > 1)
    error('EU2616:Input', 'operator probabilities must be finite and within [0,1]');
end
if abs(sum(probabilities) - 1) > 1e-12
    error('EU2616:Input', 'operator probabilities must sum to one');
end
if ~isscalar(state.best_average_fitness) || ~isnumeric(state.best_average_fitness) || ...
        ~isfinite(state.best_average_fitness) || ~isscalar(state.best_fitness) || ...
        ~isnumeric(state.best_fitness) || ~isfinite(state.best_fitness)
    error('EU2616:Input', 'fitness state must be finite scalar values');
end
validate_integer(state.last_best_generation, 0, 'last_best_generation');
end

function validate_integer(value, minimum, label)
if ~isscalar(value) || ~isnumeric(value) || ~isfinite(value) || ...
        value ~= fix(value) || value < minimum
    error('EU2616:Input', '%s must be an integer >= %d', label, minimum);
end
end
