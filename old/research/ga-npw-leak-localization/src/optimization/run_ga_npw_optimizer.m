function result = run_ga_npw_optimizer(observation, options)
if nargin < 2 || isempty(options)
    options = ga_npw_options();
end

lb = observation.bounds.lb;
ub = observation.bounds.ub;
nvars = numel(lb);
rng(options.Seed, 'twister');

population = deterministic_initial_population(options.PopulationSize, lb, ub, observation);
fitness = evaluate_population(population, observation);

[bestObjective, bestIdx] = min(fitness);
bestX = population(bestIdx, :);
initialBestObjective = bestObjective;

history.bestObjective = zeros(options.MaxGenerations, 1);
history.meanObjective = zeros(options.MaxGenerations, 1);

for generation = 1:options.MaxGenerations
    nextPopulation = zeros(size(population));
    row = 1;
    while row <= options.PopulationSize
        parent1 = tournament_parent(population, fitness, options.TournamentSize);
        parent2 = tournament_parent(population, fitness, options.TournamentSize);

        if rand < options.CrossoverRate
            alpha = rand(1, nvars);
            child1 = alpha .* parent1 + (1 - alpha) .* parent2;
            child2 = alpha .* parent2 + (1 - alpha) .* parent1;
        else
            child1 = parent1;
            child2 = parent2;
        end

        child1 = mutate_child(child1, lb, ub, options);
        child2 = mutate_child(child2, lb, ub, options);

        nextPopulation(row, :) = child1;
        if row + 1 <= options.PopulationSize
            nextPopulation(row + 1, :) = child2;
        end
        row = row + 2;
    end

    population = nextPopulation;
    fitness = evaluate_population(population, observation);

    [generationBestObjective, generationBestIdx] = min(fitness);
    if generationBestObjective < bestObjective
        bestObjective = generationBestObjective;
        bestX = population(generationBestIdx, :);
    end

    history.bestObjective(generation) = bestObjective;
    history.meanObjective(generation) = mean(fitness);
end

[~, details] = ga_npw_fitness(bestX, observation);
result = struct();
result.method = 'GA-NPW';
result.options = options;
result.best_x = bestX;
result.best_objective = bestObjective;
result.initial_best_objective = initialBestObjective;
result.history = history;
result.details = details;
result.predicted_leak_position_m = bestX(1);
result.predicted_wave_speed_mps = bestX(2);
result.predicted_velocity_mps = bestX(3);
result.predicted_sync_offset_s = bestX(4);
end

function fitness = evaluate_population(population, observation)
fitness = zeros(size(population, 1), 1);
for i = 1:size(population, 1)
    fitness(i) = ga_npw_fitness(population(i, :), observation);
end
end

function parent = tournament_parent(population, fitness, tournamentSize)
idx = randi(size(population, 1), tournamentSize, 1);
[~, localBest] = min(fitness(idx));
parent = population(idx(localBest), :);
end

function child = mutate_child(child, lb, ub, options)
range = ub - lb;
for j = 1:numel(child)
    if rand < options.MutationRate
        child(j) = child(j) + options.MutationScale(j) * range(j) * randn;
    end
end
child = min(max(child, lb), ub);
end

function population = deterministic_initial_population(populationSize, lb, ub, observation)
nvars = numel(lb);
population = zeros(populationSize, nvars);

baselineX = npw_position_from_delta_t( ...
    observation.observed_delta_t_s, ...
    observation.nominal_wave_speed_mps, ...
    observation.nominal_velocity_mps, ...
    observation.pipeline_length_m, ...
    observation.nominal_sync_offset_s);

population(1, :) = min(max([baselineX, observation.nominal_wave_speed_mps, observation.nominal_velocity_mps, 0], lb), ub);
population(2, :) = min(max([baselineX, observation.measured_wave_speed_mps, observation.measured_velocity_mps, observation.measured_sync_offset_s], lb), ub);
population(3, :) = lb;
population(4, :) = ub;

bases = [2, 3, 5, 7];
for i = 5:populationSize
    q = zeros(1, nvars);
    for j = 1:nvars
        q(j) = van_der_corput(i - 4, bases(j));
    end
    population(i, :) = lb + q .* (ub - lb);
end
end

function value = van_der_corput(index, base)
value = 0;
denominator = 1;
while index > 0
    denominator = denominator * base;
    remainder = mod(index, base);
    value = value + remainder / denominator;
    index = floor(index / base);
end
end
