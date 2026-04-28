function testReport = run_unit_tests_impl()
projectRoot = fileparts(fileparts(mfilename('fullpath')));
addpath(genpath(fullfile(projectRoot, 'src')));

passCount = 0;

structureReport = verify_project_structure(projectRoot);
assert(structureReport.passed, 'Project structure check failed.');
passCount = passCount + 1;

network = ieee33_synthetic_network();
assert(network.node_count == 33, 'IEEE33 synthetic network must have 33 nodes.');
assert(network.section_count == 32, 'IEEE33 synthetic network must have 32 fault sections.');
passCount = passCount + 1;

sig9 = fault_signature(network, 9, network.sensor_nodes);
sig10 = fault_signature(network, 10, network.sensor_nodes);
assert(numel(sig9) == numel(network.sensor_nodes), 'Signature length must match sensor count.');
assert(any(sig9 ~= sig10), 'Adjacent sections should have distinguishable signatures with full FTUs.');
passCount = passCount + 1;

caseData = synthetic_fault_cases('unit');
observation = build_fault_observation(caseData);
[trueObjective, decodedTrue] = fault_objective(section_vector(network.section_count, observation.true_fault_section), observation);
[wrongObjective, ~] = fault_objective(section_vector(network.section_count, 1), observation);
assert(decodedTrue == observation.true_fault_section, 'Objective decoder should recover one-hot true section.');
assert(trueObjective <= wrongObjective, 'True section objective should not be worse than wrong section.');
passCount = passCount + 1;

psoOptions = spso_ga_options('PSO-GA', 20260428);
spsoOptions = spso_ga_options('SPSO-GA', 20260428);
article = article_reported();
assert(psoOptions.PopulationSize == article.algorithm.population_size, 'Population size mismatch.');
assert(psoOptions.Iterations == article.algorithm.iterations, 'Iteration count mismatch.');
assert(abs(spsoOptions.Omega - article.algorithm.spso_ga.omega) < eps, 'SPSO omega mismatch.');
passCount = passCount + 1;

resultA = run_spso_ga_optimizer(observation, spsoOptions);
resultB = run_spso_ga_optimizer(observation, spsoOptions);
assert(resultA.predicted_fault_section == observation.true_fault_section, 'SPSO-GA should solve deterministic unit case.');
assert(resultA.predicted_fault_section == resultB.predicted_fault_section, 'Same seed should reproduce fault section.');
assert(abs(resultA.best_fitness - resultB.best_fitness) < 1.0e-12, 'Same seed should reproduce objective.');
passCount = passCount + 1;

metrics = fault_location_metrics([1, 2, 3], [1, 4, 3]);
assert(abs(metrics.accuracy_percent - 66.6666666667) < 1.0e-6, 'Accuracy metric mismatch.');
passCount = passCount + 1;

testReport = struct();
testReport.passed = true;
testReport.pass_count = passCount;
testReport.note = 'Deterministic SPSO-GA unit tests passed.';

fprintf('Unit tests passed: %d\n', passCount);
end

function x = section_vector(n, section)
x = zeros(1, n);
x(section) = 1;
end
