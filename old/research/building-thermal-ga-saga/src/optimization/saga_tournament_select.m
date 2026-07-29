function selected = saga_tournament_select(population, fitness, tournamentSize)
idx = randi(numel(population), tournamentSize, 1);
[~, bestLocal] = min(fitness(idx));
selected = population(idx(bestLocal));
assert(isfield(selected, 'x') && isfield(selected, 'theta'), ...
    'SAGA selection must return a complete individual.');
end
