function result = run_saga_optimizer(problem, options)
if nargin < 2 || isempty(options)
    options = saga_building_options();
end

rng(options.Seed, 'twister');
population = initialize_saga_population(problem, options);
[population, fitness] = evaluate_saga_population(population, problem);
[bestObjective, bestIdx] = min(fitness);
bestIndividual = population(bestIdx);
initialBestObjective = bestObjective;

history.best_objective = zeros(options.MaxGenerations, 1);
history.mean_objective = zeros(options.MaxGenerations, 1);
history.best_x = zeros(options.MaxGenerations, problem.nvars);
history.Pm_history = zeros(options.MaxGenerations, 1);
history.Pc_history = zeros(options.MaxGenerations, 1);
history.sigma_history = zeros(options.MaxGenerations, 1);
history.theta_best_individual_history = zeros(options.MaxGenerations, 3);
history.theta_population_history = zeros(options.PopulationSize, 3, options.MaxGenerations);
history.theta_variance_history = zeros(options.MaxGenerations, 3);
functionEvaluations = options.PopulationSize;

for generation = 1:options.MaxGenerations
    nextPopulation = population;
    [~, order] = sort(fitness);
    eliteCount = min(options.EliteCount, options.PopulationSize);
    nextPopulation(1:eliteCount) = population(order(1:eliteCount));

    row = eliteCount + 1;
    while row <= options.PopulationSize
        parent1 = saga_tournament_select(population, fitness, options.TournamentSize);
        parent2 = saga_tournament_select(population, fitness, options.TournamentSize);
        [child1, child2] = saga_variation(parent1, parent2, problem, options);

        nextPopulation(row) = child1;
        if row + 1 <= options.PopulationSize
            nextPopulation(row + 1) = child2;
        end
        row = row + 2;
    end

    population = nextPopulation;
    [population, fitness] = evaluate_saga_population(population, problem);
    functionEvaluations = functionEvaluations + options.PopulationSize;

    [generationBestObjective, generationBestIdx] = min(fitness);
    if generationBestObjective < bestObjective
        bestObjective = generationBestObjective;
        bestIndividual = population(generationBestIdx);
    end

    thetaMatrix = saga_theta_matrix(population);
    bestTheta = theta_to_vector(bestIndividual.theta);
    history.best_objective(generation) = bestObjective;
    history.mean_objective(generation) = mean(fitness);
    history.best_x(generation, :) = bestIndividual.x;
    history.Pm_history(generation) = bestIndividual.theta.Pm;
    history.Pc_history(generation) = bestIndividual.theta.Pc;
    history.sigma_history(generation) = bestIndividual.theta.sigma;
    history.theta_best_individual_history(generation, :) = bestTheta;
    history.theta_population_history(:, :, generation) = thetaMatrix;
    history.theta_variance_history(generation, :) = var(thetaMatrix, 0, 1);
end

[~, details] = building_surrogate_objective(bestIndividual.x, problem);

result = struct();
result.method = 'formal_saga';
result.genotype_type = options.GenotypeType;
result.problem_case_id = problem.case.id;
result.problem_case_label = problem.case.label;
result.no_cooling = problem.no_cooling;
result.options = options;
result.best_individual = bestIndividual;
result.best_x = bestIndividual.x;
result.best_theta = bestIndividual.theta;
result.best_design = decode_building_genome(bestIndividual.x, problem.design_space);
result.best_objective = bestObjective;
result.best_lcc_eur = details.lcc_eur;
result.initial_best_objective = initialBestObjective;
result.history = history;
result.function_evaluations = functionEvaluations;
result.details = details;
result.diagnostics.theta_in_genotype = true;
result.diagnostics.theta_is_base_ga_parameters = true;
result.diagnostics.variation_receives_complete_individual = true;
result.diagnostics.variation_changes_theta = true;
result.diagnostics.selection_returns_complete_individual = true;
result.diagnostics.external_theta_update = false;
result.diagnostics.generation_based_theta_update = false;
result.diagnostics.stagnation_based_theta_update = false;
result.diagnostics.diversity_based_theta_update = false;
end

function [population, fitness] = evaluate_saga_population(population, problem)
fitness = zeros(numel(population), 1);
for i = 1:numel(population)
    fitness(i) = building_surrogate_objective(population(i).x, problem);
    population(i).fitness = fitness(i);
end
end
