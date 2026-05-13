function result = run_evolutionary_optimizer(observation, options, maxGenerations)
if isfield(options, 'ObjectiveMode')
    observation.objective_mode = options.ObjectiveMode;
end
lb = observation.bounds.lb;
ub = observation.bounds.ub;
rng(options.Seed, 'twister');
runTimer = tic;

population = initialize_population(options.PopulationSize, lb, ub, observation);
fitness = evaluate_population(population, observation);
[bestObjective, bestIdx] = min(fitness);
bestX = population(bestIdx, :);
initialBestObjective = bestObjective;
generationToBest = 0;
stagnationCount = 0;

history.bestObjective = zeros(maxGenerations, 1);
history.meanObjective = zeros(maxGenerations, 1);
history.crossoverRate = zeros(maxGenerations, 1);
history.mutationRate = zeros(maxGenerations, 1);
history.populationDiversity = zeros(maxGenerations, 1);
history.stagnationCount = zeros(maxGenerations, 1);

for generation = 1:maxGenerations
    [fitness, order] = sort(fitness);
    population = population(order, :);
    if fitness(1) < bestObjective
        bestObjective = fitness(1);
        bestX = population(1, :);
        generationToBest = generation - 1;
        stagnationCount = 0;
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
        generationToBest = generation;
        stagnationCount = 0;
    else
        stagnationCount = stagnationCount + 1;
    end

    history.bestObjective(generation) = bestObjective;
    history.meanObjective(generation) = mean(fitness);
    history.crossoverRate(generation) = crossoverRate;
    history.mutationRate(generation) = mutationRate;
    history.populationDiversity(generation) = population_diversity(population, lb, ub);
    history.stagnationCount(generation) = stagnationCount;
end

runtimeSeconds = toc(runTimer);
history.generationToBest = generationToBest;
history.runtimeSeconds = runtimeSeconds;

[~, details] = source_objective(bestX, observation);
result = struct();
result.method = options.Method;
result.options = options;
result.generations = maxGenerations;
result.best_x = bestX;
result.best_objective = bestObjective;
result.initial_best_objective = initialBestObjective;
result.generation_to_best = generationToBest;
result.runtime_seconds = runtimeSeconds;
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
[agp, agpFitness, egp, ~, agpCount] = article_gene_pool_split(population, fitness, options.Beta);
articleExact = isfield(options, 'OperatorMode') && strcmpi(options.OperatorMode, 'article_exact');

nextPopulation = zeros(size(population));
nextPopulation(1, :) = population(1, :);
row = 2;

while row <= populationSize
    parent1 = tournament_parent(agp, agpFitness, min(options.TournamentSize, agpCount));
    parent2 = tournament_parent(agp, agpFitness, min(options.TournamentSize, agpCount));

    if rand < crossoverRate
        if articleExact
            child1 = options.Beta .* parent1 + (1 - options.Beta) .* parent2;
            child2 = options.Beta .* parent2 + (1 - options.Beta) .* parent1;
        else
            blend = rand(size(parent1));
            child1 = blend .* parent1 + (1 - blend) .* parent2;
            child2 = blend .* parent2 + (1 - blend) .* parent1;
        end
    elseif articleExact && generation < options.SetMax && ~isempty(egp)
        egpParent1 = egp(randi(size(egp, 1)), :);
        egpParent2 = egp(randi(size(egp, 1)), :);
        child1 = article_egp_crossover(parent1, egpParent1, options.EGPInheritanceRate);
        child2 = article_egp_crossover(parent2, egpParent2, options.EGPInheritanceRate);
    elseif articleExact
        if rand < options.Gamma
            best = population(1, :);
            child1 = best + options.Gamma .* (parent1 - best);
            child2 = best + options.Gamma .* (parent2 - best);
        else
            child1 = active_search_child(population(1, :), lb, ub);
            child2 = active_search_child(population(1, :), lb, ub);
        end
    else
        if ~isempty(egp) && rand < options.Gamma
            parent2 = egp(randi(size(egp, 1)), :);
        end
        child1 = parent1;
        child2 = parent2;
    end

    child1 = mutate_nonuniform(child1, lb, ub, mutationRate, generation, maxGenerations, options.NMGAScheduleExponent);
    child2 = mutate_nonuniform(child2, lb, ub, mutationRate, generation, maxGenerations, options.NMGAScheduleExponent);
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

function child = active_search_child(best, lb, ub)
step = 0.02 .* (ub - lb) .* (rand(size(best)) - 0.5);
child = min(max(best + step, lb), ub);
end

function child = mutate_uniform(child, lb, ub, mutationRate, stepScale)
for j = 1:numel(child)
    if rand < mutationRate
        child(j) = child(j) + stepScale(j) .* randn;
    end
end
child = min(max(child, lb), ub);
end

function child = mutate_nonuniform(child, lb, ub, mutationRate, generation, maxGenerations, exponent)
if nargin < 7 || isempty(exponent)
    exponent = 2;
end
for j = 1:numel(child)
    if rand < mutationRate
        direction = sign(rand - 0.5);
        if direction >= 0
            distance = ub(j) - child(j);
        else
            distance = child(j) - lb(j);
        end
        child(j) = child(j) + direction .* article_nonuniform_delta(distance, generation, maxGenerations, exponent, rand);
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

function diversity = population_diversity(population, lb, ub)
span = max(ub - lb, eps);
centered = population - mean(population, 1);
normalized = centered ./ span;
diversity = mean(sqrt(sum(normalized .^ 2, 2)));
if ~isfinite(diversity)
    diversity = 0;
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
