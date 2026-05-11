function testReport = run_unit_tests_impl()
projectRoot = fileparts(fileparts(mfilename('fullpath')));
addpath(genpath(fullfile(projectRoot, 'src')));

passCount = 0;

structureReport = verify_project_structure(projectRoot);
assert(structureReport.passed, 'Project structure check failed.');
passCount = passCount + 1;

cases = building_cases(7);
scenario = synthetic_sandbox_scenarios();
problem = building_problem(cases(1), false, scenario(1));
gaOptions = ga_building_options(1234);
gaOptions.PopulationSize = 18;
gaOptions.MaxGenerations = 12;
sagaOptions = saga_building_options(1234);
sagaOptions.PopulationSize = 18;
sagaOptions.MaxGenerations = 12;

population = initialize_saga_population(problem, sagaOptions);
assert(isfield(population(1), 'x') && isfield(population(1), 'theta'), 'SAGA individual lacks x or theta.');
passCount = passCount + 1;

thetaFields = sort(fieldnames(population(1).theta));
assert(isequal(thetaFields, sort({'Pm'; 'Pc'; 'sigma'})), 'Theta contains non-base GA parameters.');
passCount = passCount + 1;

thetaMatrix = saga_theta_matrix(population);
assert(max(max(abs(thetaMatrix - repmat(thetaMatrix(1, :), size(thetaMatrix, 1), 1)))) > 0, ...
    'Theta appears global rather than individual.');
passCount = passCount + 1;

testOptions = sagaOptions;
testOptions.ThetaMutationRate = 1.0;
testOptions.ThetaMutationScale = [0.10, 0.10, 0.80];
population(1).theta = struct('Pm', 1.0, 'Pc', 1.0, 'sigma', 2.0);
population(2).theta = struct('Pm', 1.0, 'Pc', 1.0, 'sigma', 2.0);
[child1, child2, trace] = saga_variation(population(1), population(2), problem, testOptions);
assert(trace.received_complete_individual, 'Variation did not receive complete individual.');
passCount = passCount + 1;

assert(any(child1.x ~= population(1).x) || any(child2.x ~= population(2).x), 'Variation did not change x.');
passCount = passCount + 1;

assert(trace.theta_changed, 'Theta mutation/crossover did not change theta under controlled seed.');
passCount = passCount + 1;

thetaA = struct('Pm', 0.10, 'Pc', 0.70, 'sigma', 1.0);
thetaB = struct('Pm', 0.30, 'Pc', 0.90, 'sigma', 3.0);
childTheta = saga_crossover_theta(thetaA, thetaB, [true, false, true]);
assert(abs(childTheta.Pm - thetaB.Pm) < eps && abs(childTheta.Pc - thetaA.Pc) < eps && ...
    abs(childTheta.sigma - thetaB.sigma) < eps, 'Theta crossover did not inherit from parents.');
passCount = passCount + 1;

childThetaValues = [child1.theta.Pm, child1.theta.Pc, child1.theta.sigma; child2.theta.Pm, child2.theta.Pc, child2.theta.sigma];
assert(all(childThetaValues(:, 1) >= sagaOptions.ThetaBounds.Pm(1)) && all(childThetaValues(:, 1) <= sagaOptions.ThetaBounds.Pm(2)) && ...
    all(childThetaValues(:, 2) >= sagaOptions.ThetaBounds.Pc(1)) && all(childThetaValues(:, 2) <= sagaOptions.ThetaBounds.Pc(2)) && ...
    all(childThetaValues(:, 3) >= sagaOptions.ThetaBounds.sigma(1)) && all(childThetaValues(:, 3) <= sagaOptions.ThetaBounds.sigma(2)), ...
    'Theta left configured bounds.');
passCount = passCount + 1;

fitness = (1:numel(population))';
selected = saga_tournament_select(population, fitness, 3);
assert(isfield(selected, 'x') && isfield(selected, 'theta'), 'Selection did not return complete individual.');
passCount = passCount + 1;

selectedTheta = theta_to_vector(selected.theta);
populationTheta = saga_theta_matrix(population);
assert(any(all(abs(populationTheta - repmat(selectedTheta, size(populationTheta, 1), 1)) < 1.0e-12, 2)), ...
    'Selection recreated theta externally.');
passCount = passCount + 1;

sagaResultA = run_saga_optimizer(problem, sagaOptions);
assert(~sagaResultA.diagnostics.generation_based_theta_update, 'SAGA has generation-based theta update.');
passCount = passCount + 1;

assert(~sagaResultA.diagnostics.stagnation_based_theta_update, 'SAGA has stagnation-based theta update.');
passCount = passCount + 1;

assert(~sagaResultA.diagnostics.diversity_based_theta_update, 'SAGA has diversity-based theta update.');
passCount = passCount + 1;

sagaResultB = run_saga_optimizer(problem, sagaOptions);
assert(max(abs(sagaResultA.best_x - sagaResultB.best_x)) < 1.0e-12, 'SAGA x is not reproducible.');
assert(abs(sagaResultA.best_objective - sagaResultB.best_objective) < 1.0e-12, 'SAGA objective is not reproducible.');
passCount = passCount + 1;

assert(all(sagaResultA.best_x >= problem.lb - 1.0e-12) && all(sagaResultA.best_x <= problem.ub + 1.0e-12), ...
    'SAGA output violates problem bounds.');
passCount = passCount + 1;

assert(isfield(sagaResultA.history, 'theta_population_history') && ~isempty(sagaResultA.history.theta_population_history), ...
    'SAGA does not log theta history.');
passCount = passCount + 1;

assert(size(sagaResultA.history.theta_population_history, 3) == sagaOptions.MaxGenerations, ...
    'Theta history length does not equal generation count.');
passCount = passCount + 1;

assert(isfield(sagaResultA.best_individual, 'x') && isfield(sagaResultA.best_individual, 'theta'), ...
    'Best SAGA individual lacks x or theta.');
passCount = passCount + 1;

criterion = satisfies_saga_criterion(sagaResultA);
assert(criterion.passed, criterion.message);
passCount = passCount + 1;

gaResultA = run_classical_ga(problem, gaOptions);
assert(strcmp(gaResultA.genotype_type, 'x_only') && ~isfield(gaResultA, 'best_theta'), ...
    'Classical GA is not x-only.');
passCount = passCount + 1;

assert(gaResultA.options.MutationRate == gaOptions.MutationRate && gaResultA.diagnostics.fixed_mutation_probability, ...
    'Classical GA does not use fixed mutation probability.');
passCount = passCount + 1;

assert(gaResultA.options.CrossoverRate == gaOptions.CrossoverRate && gaResultA.diagnostics.fixed_crossover_probability, ...
    'Classical GA does not use fixed crossover probability.');
passCount = passCount + 1;

assert(all(gaResultA.best_x >= problem.lb - 1.0e-12) && all(gaResultA.best_x <= problem.ub + 1.0e-12), ...
    'Classical GA output violates problem bounds.');
passCount = passCount + 1;

gaResultB = run_classical_ga(problem, gaOptions);
assert(max(abs(gaResultA.best_x - gaResultB.best_x)) < 1.0e-12, 'Classical GA x is not reproducible.');
assert(abs(gaResultA.best_objective - gaResultB.best_objective) < 1.0e-12, 'Classical GA objective is not reproducible.');
passCount = passCount + 1;

classification = classify_article_sga();
assert(~classification.is_formal_saga && classification.external_theta_update, ...
    'Article fuzzy SGA classification should fail the formal local SAGA criterion.');
passCount = passCount + 1;

defaults = ga_building_options(1);
reported = article_reported();
assert(defaults.PopulationSize == reported.ga.population_size && defaults.MaxGenerations == reported.ga.generations, ...
    'Default GA budget does not match article-reported population/generation count.');
passCount = passCount + 1;

testReport = struct();
testReport.passed = true;
testReport.pass_count = passCount;
testReport.note = 'Classical GA and formal SAGA unit tests passed.';

fprintf('Unit tests passed: %d\n', passCount);
end
