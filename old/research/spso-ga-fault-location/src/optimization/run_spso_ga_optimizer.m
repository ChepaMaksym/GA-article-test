function result = run_spso_ga_optimizer(observation, options)
if nargin < 2 || isempty(options)
    options = spso_ga_options('SPSO-GA');
end

rng(options.Seed, 'twister');
nvars = observation.network.section_count;
population = initialize_particles(options.PopulationSize, nvars, observation);
velocity = 0.10 * randn(options.PopulationSize, nvars);
fitness = evaluate_population(population, observation);

personalBest = population;
personalBestFitness = fitness;
[globalBestFitness, bestIdx] = min(fitness);
globalBest = population(bestIdx, :);
initialBestFitness = globalBestFitness;

history.bestFitness = zeros(options.Iterations, 1);
history.meanFitness = zeros(options.Iterations, 1);

for iteration = 1:options.Iterations
    r1 = rand(size(population));
    r2 = rand(size(population));
    velocity = options.Omega .* velocity ...
        + options.C1 .* r1 .* (personalBest - population) ...
        + options.C2 .* r2 .* (globalBest - population);
    population = min(max(population + velocity, 0), 1);

    if strcmpi(options.Method, 'SPSO-GA')
        population = successive_refine_population(population, globalBest, iteration, options);
    end

    if mod(iteration, max(1, round(options.Iterations / 5))) == 0
        population = ga_substep(population, fitness, observation, options);
    end

    fitness = evaluate_population(population, observation);
    improved = fitness < personalBestFitness;
    personalBest(improved, :) = population(improved, :);
    personalBestFitness(improved) = fitness(improved);
    [iterationBest, bestIdx] = min(fitness);
    if iterationBest < globalBestFitness
        globalBestFitness = iterationBest;
        globalBest = population(bestIdx, :);
    end

    history.bestFitness(iteration) = globalBestFitness;
    history.meanFitness(iteration) = mean(fitness);
end

[~, decodedSection] = fault_objective(globalBest, observation);
result = struct();
result.method = options.Method;
result.options = options;
result.best_position = globalBest;
result.best_fitness = globalBestFitness;
result.initial_best_fitness = initialBestFitness;
result.predicted_fault_section = decodedSection;
result.history = history;
result.correct = decodedSection == observation.true_fault_section;
result.section_error = abs(decodedSection - observation.true_fault_section);
end

function population = initialize_particles(populationSize, nvars, observation)
population = rand(populationSize, nvars);
signatureScores = zeros(1, nvars);
for s = 1:nvars
    predicted = fault_signature(observation.network, s, observation.sensor_nodes);
    signatureScores(s) = -sum(abs(predicted - observation.observed_signature));
end
signatureScores = signatureScores - min(signatureScores);
if max(signatureScores) > 0
    signatureScores = signatureScores ./ max(signatureScores);
end
population(1, :) = signatureScores;
for s = 1:min(nvars, populationSize - 1)
    population(s + 1, s) = 1;
end
end

function population = successive_refine_population(population, globalBest, iteration, options)
blend = min(0.65, 0.15 + 0.50 * iteration / options.Iterations);
for i = 2:size(population, 1)
    if rand < 0.35
        population(i, :) = (1 - blend) .* population(i, :) + blend .* globalBest;
    end
end
population = min(max(population, 0), 1);
end

function population = ga_substep(population, fitness, observation, options)
[~, order] = sort(fitness);
population = population(order, :);
eliteCount = max(2, round(0.20 * size(population, 1)));
nextPopulation = population;
row = eliteCount + 1;
while row <= size(population, 1)
    parent1 = tournament_parent(population, fitness(order), 3);
    parent2 = tournament_parent(population, fitness(order), 3);
    if rand < options.CrossoverProbability
        cut = randi(size(population, 2) - 1);
        child = [parent1(1:cut), parent2(cut + 1:end)];
    else
        child = parent1;
    end
    if rand < options.MutationProbability
        idx = randi(size(population, 2));
        child(idx) = min(max(child(idx) + options.MutationScale * randn, 0), 1);
    end
    nextPopulation(row, :) = child;
    row = row + 1;
end
population = nextPopulation;

% Keep a deterministic signature-driven candidate in each GA substep.
candidate = zeros(1, observation.network.section_count);
scores = zeros(1, observation.network.section_count);
for s = 1:observation.network.section_count
    predicted = fault_signature(observation.network, s, observation.sensor_nodes);
    scores(s) = -sum(abs(predicted - observation.observed_signature));
end
[~, bestSection] = max(scores);
candidate(bestSection) = 1;
population(end, :) = candidate;
end

function fitness = evaluate_population(population, observation)
fitness = zeros(size(population, 1), 1);
for i = 1:size(population, 1)
    fitness(i) = fault_objective(population(i, :), observation);
end
end

function parent = tournament_parent(population, fitness, tournamentSize)
idx = randi(size(population, 1), tournamentSize, 1);
[~, localBest] = min(fitness(idx));
parent = population(idx(localBest), :);
end
