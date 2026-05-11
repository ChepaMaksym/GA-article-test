function result = run_classical_ga(problem, options)
if nargin < 2 || isempty(options)
    options = ga_building_options();
end

rng(options.Seed, 'twister');
population = initialize_ga_population(problem, options);
fitness = evaluate_ga_population(population, problem);
[bestObjective, bestIdx] = min(fitness);
bestX = population(bestIdx, :);
initialBestObjective = bestObjective;

history.best_objective = zeros(options.MaxGenerations, 1);
history.mean_objective = zeros(options.MaxGenerations, 1);
history.best_x = zeros(options.MaxGenerations, problem.nvars);
functionEvaluations = options.PopulationSize;

for generation = 1:options.MaxGenerations
    nextPopulation = zeros(size(population));
    [~, order] = sort(fitness);
    eliteCount = min(options.EliteCount, options.PopulationSize);
    nextPopulation(1:eliteCount, :) = population(order(1:eliteCount), :);

    row = eliteCount + 1;
    while row <= options.PopulationSize
        parent1 = tournament_select_x(population, fitness, options.TournamentSize);
        parent2 = tournament_select_x(population, fitness, options.TournamentSize);

        [child1, child2] = ga_uniform_crossover(parent1, parent2, options.CrossoverRate);
        child1 = mutate_discrete_genome(child1, problem, options.MutationRate, options.MutationStep);
        child2 = mutate_discrete_genome(child2, problem, options.MutationRate, options.MutationStep);

        nextPopulation(row, :) = child1;
        if row + 1 <= options.PopulationSize
            nextPopulation(row + 1, :) = child2;
        end
        row = row + 2;
    end

    population = nextPopulation;
    fitness = evaluate_ga_population(population, problem);
    functionEvaluations = functionEvaluations + options.PopulationSize;

    [generationBestObjective, generationBestIdx] = min(fitness);
    if generationBestObjective < bestObjective
        bestObjective = generationBestObjective;
        bestX = population(generationBestIdx, :);
    end

    history.best_objective(generation) = bestObjective;
    history.mean_objective(generation) = mean(fitness);
    history.best_x(generation, :) = bestX;
end

[~, details] = building_surrogate_objective(bestX, problem);

result = struct();
result.method = 'classical_ga';
result.genotype_type = options.GenotypeType;
result.problem_case_id = problem.case.id;
result.problem_case_label = problem.case.label;
result.no_cooling = problem.no_cooling;
result.options = options;
result.best_x = bestX;
result.best_design = decode_building_genome(bestX, problem.design_space);
result.best_objective = bestObjective;
result.best_lcc_eur = details.lcc_eur;
result.initial_best_objective = initialBestObjective;
result.history = history;
result.function_evaluations = functionEvaluations;
result.details = details;
result.diagnostics.fixed_mutation_probability = true;
result.diagnostics.fixed_crossover_probability = true;
result.diagnostics.theta_in_genotype = false;
end

function fitness = evaluate_ga_population(population, problem)
fitness = zeros(size(population, 1), 1);
for i = 1:size(population, 1)
    fitness(i) = building_surrogate_objective(population(i, :), problem);
end
end

function parent = tournament_select_x(population, fitness, tournamentSize)
idx = randi(size(population, 1), tournamentSize, 1);
[~, bestLocal] = min(fitness(idx));
parent = population(idx(bestLocal), :);
end

function [child1, child2] = ga_uniform_crossover(parent1, parent2, crossoverRate)
child1 = parent1;
child2 = parent2;
if rand < crossoverRate
    mask = rand(size(parent1)) < 0.5;
    child1(mask) = parent2(mask);
    child2(mask) = parent1(mask);
end
end
