function result = run_evolutionary_optimizer(observation, options, maxGenerations)
lb = observation.bounds.lb;
ub = observation.bounds.ub;
rng(options.Seed, 'twister');

population = initialize_population(options.PopulationSize, lb, ub, observation);
fitness = evaluate_population(population, observation);
[bestObjective, bestIdx] = min(fitness);
bestX = population(bestIdx, :);
initialBestObjective = bestObjective;

history.bestObjective = zeros(maxGenerations, 1);
history.meanObjective = zeros(maxGenerations, 1);
history.crossoverRate = zeros(maxGenerations, 1);
history.mutationRate = zeros(maxGenerations, 1);

for generation = 1:maxGenerations
    [fitness, order] = sort(fitness);
    population = population(order, :);
    if fitness(1) < bestObjective
        bestObjective = fitness(1);
        bestX = population(1, :);
    end

    if strcmpi(options.Method, 'NMGA')
        [crossoverRate, mutationRate] = nmga_adaptive_rates(generation, maxGenerations, options);
        nextPopulation = breed_nmga(population, fitness, lb, ub, options, crossoverRate, mutationRate, generation, maxGenerations);
    else
        crossoverRate = options.MGACrossoverRate;
        mutationRate = options.MGAMutationRate;
        nextPopulation = breed_mga(population, fitness, lb, ub, options, crossoverRate, mutationRate);
    end

    population = nextPopulation;
    fitness = evaluate_population(population, observation);
    generationBest = min(fitness);
    if generationBest < bestObjective
        [bestObjective, bestIdx] = min(fitness);
        bestX = population(bestIdx, :);
    end

    history.bestObjective(generation) = bestObjective;
    history.meanObjective(generation) = mean(fitness);
    history.crossoverRate(generation) = crossoverRate;
    history.mutationRate(generation) = mutationRate;
end

[~, details] = source_objective(bestX, observation);
result = struct();
result.method = options.Method;
result.options = options;
result.generations = maxGenerations;
result.best_x = bestX;
result.best_objective = bestObjective;
result.initial_best_objective = initialBestObjective;
result.history = history;
result.details = details;
result.metrics = source_estimation_metrics(observation.true_source, bestX);
end

function population = initialize_population(populationSize, lb, ub, observation)
nvars = numel(lb);
population = zeros(populationSize, nvars);
sensorGuess = heuristic_sensor_guess(observation, lb, ub);
population(1, :) = sensorGuess;
population(2, :) = min(max([0, 0, 12000, 2.5], lb), ub);
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

function nextPopulation = breed_mga(population, fitness, lb, ub, options, crossoverRate, mutationRate)
populationSize = size(population, 1);
nvars = size(population, 2);
nextPopulation = zeros(size(population));
eliteCount = max(2, round((1 - options.Beta) * 0.25 * populationSize));
nextPopulation(1:eliteCount, :) = population(1:eliteCount, :);
row = eliteCount + 1;

while row <= populationSize
    parent1 = tournament_parent(population, fitness, options.TournamentSize);
    parent2 = tournament_parent(population, fitness, options.TournamentSize);
    if rand < crossoverRate
        alpha = options.Beta;
        child1 = alpha .* parent1 + (1 - alpha) .* parent2;
        child2 = alpha .* parent2 + (1 - alpha) .* parent1;
    else
        child1 = parent1;
        child2 = parent2;
    end
    child1 = mutate_uniform(child1, lb, ub, mutationRate, 0.05 * (ub - lb));
    child2 = mutate_uniform(child2, lb, ub, mutationRate, 0.05 * (ub - lb));
    nextPopulation(row, :) = child1;
    if row + 1 <= populationSize
        nextPopulation(row + 1, :) = child2;
    end
    row = row + 2;
end

nextPopulation = nextPopulation(:, 1:nvars);
end

function nextPopulation = breed_nmga(population, fitness, lb, ub, options, crossoverRate, mutationRate, generation, maxGenerations)
populationSize = size(population, 1);
agpCount = max(2, round(options.Beta * populationSize));
agp = population(1:agpCount, :);
agpFitness = fitness(1:agpCount);
egp = population(agpCount + 1:end, :);

nextPopulation = zeros(size(population));
nextPopulation(1, :) = population(1, :);
row = 2;

while row <= populationSize
    parent1 = tournament_parent(agp, agpFitness, min(options.TournamentSize, agpCount));
    if ~isempty(egp) && rand < options.Gamma
        parent2 = egp(randi(size(egp, 1)), :);
    else
        parent2 = tournament_parent(agp, agpFitness, min(options.TournamentSize, agpCount));
    end

    if rand < crossoverRate
        blend = rand(size(parent1));
        child1 = blend .* parent1 + (1 - blend) .* parent2;
        child2 = blend .* parent2 + (1 - blend) .* parent1;
    else
        child1 = parent1;
        child2 = parent2;
    end

    child1 = mutate_nonuniform(child1, lb, ub, mutationRate, generation, maxGenerations);
    child2 = mutate_nonuniform(child2, lb, ub, mutationRate, generation, maxGenerations);
    nextPopulation(row, :) = child1;
    if row + 1 <= populationSize
        nextPopulation(row + 1, :) = child2;
    end
    row = row + 2;
end

if mod(generation, options.SetMax) == 0
    q = rand(1, size(population, 2));
    nextPopulation(end, :) = lb + q .* (ub - lb);
end
end

function child = mutate_uniform(child, lb, ub, mutationRate, stepScale)
for j = 1:numel(child)
    if rand < mutationRate
        child(j) = child(j) + stepScale(j) .* randn;
    end
end
child = min(max(child, lb), ub);
end

function child = mutate_nonuniform(child, lb, ub, mutationRate, generation, maxGenerations)
progress = min(max(generation ./ max(maxGenerations, 1), 0), 1);
scale = (1 - progress) .^ 1.6;
for j = 1:numel(child)
    if rand < mutationRate
        direction = sign(rand - 0.5);
        if direction >= 0
            distance = ub(j) - child(j);
        else
            distance = child(j) - lb(j);
        end
        child(j) = child(j) + direction .* distance .* (1 - rand .^ scale);
    end
end
child = min(max(child, lb), ub);
end

function fitness = evaluate_population(population, observation)
fitness = zeros(size(population, 1), 1);
for i = 1:size(population, 1)
    fitness(i) = source_objective(population(i, :), observation);
end
end

function parent = tournament_parent(population, fitness, tournamentSize)
idx = randi(size(population, 1), tournamentSize, 1);
[~, localBest] = min(fitness(idx));
parent = population(idx(localBest), :);
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

function guess = heuristic_sensor_guess(observation, lb, ub)
[~, idx] = max(observation.observed_concentration);
sourceX = observation.sensors.x_m(idx) - 65;
sourceY = observation.sensors.y_m(idx);
sourceQ = 0.5 * (lb(3) + ub(3));
sourceH = 2.0;
guess = min(max([sourceX, sourceY, sourceQ, sourceH], lb), ub);
end
