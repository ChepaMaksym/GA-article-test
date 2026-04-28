function testReport = run_unit_tests_impl()
projectRoot = fileparts(fileparts(mfilename('fullpath')));
addpath(genpath(fullfile(projectRoot, 'src')));

passCount = 0;

structureReport = verify_project_structure(projectRoot);
assert(structureReport.passed, 'Project structure check failed.');
passCount = passCount + 1;

L = 175000;
x = 70000;
a = 1120;
v = 1.2;
sync = 0.35;
deltaT = npw_delta_t(x, a, v, L, sync);
recoveredX = npw_position_from_delta_t(deltaT, a, v, L, sync);
assert(abs(recoveredX - x) < 1.0e-6, 'NPW forward/inverse equations are inconsistent.');
passCount = passCount + 1;

article = article_reported();
options = ga_npw_options(20260428);
assert(options.PopulationSize == article.ga.population_size, 'GA population size does not match article setting.');
assert(options.MaxGenerations == article.ga.iterations, 'GA iteration count does not match article setting.');
assert(abs(options.CrossoverRate - article.ga.crossover_rate) < eps, 'GA crossover rate does not match article setting.');
assert(abs(options.MutationRate - article.ga.mutation_rate) < eps, 'GA mutation rate does not match article setting.');
assert(strcmp(options.Selection, article.ga.selection), 'GA selection does not match article setting.');
passCount = passCount + 1;

unitCase = synthetic_reproduction_cases('unit');
observation = generate_npw_observation(unitCase);
resultA = run_ga_npw_optimizer(observation, options);
assert(all(resultA.best_x >= observation.bounds.lb - 1.0e-12), 'GA result is below lower bounds.');
assert(all(resultA.best_x <= observation.bounds.ub + 1.0e-12), 'GA result is above upper bounds.');
passCount = passCount + 1;

assert(resultA.best_objective < resultA.initial_best_objective, 'GA best fitness did not decrease.');
passCount = passCount + 1;

resultB = run_ga_npw_optimizer(observation, options);
assert(max(abs(resultA.best_x - resultB.best_x)) < 1.0e-9, 'GA result is not reproducible with the same seed.');
assert(abs(resultA.best_objective - resultB.best_objective) < 1.0e-12, 'GA objective is not reproducible with the same seed.');
passCount = passCount + 1;

testReport = struct();
testReport.passed = true;
testReport.pass_count = passCount;
testReport.note = 'Deterministic unit tests passed.';

fprintf('Unit tests passed: %d\n', passCount);
end
