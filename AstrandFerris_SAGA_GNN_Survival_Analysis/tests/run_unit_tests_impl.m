function testReport = run_unit_tests_impl()
projectRoot = fileparts(fileparts(mfilename('fullpath')));
addpath(genpath(fullfile(projectRoot, 'src')));

passCount = 0;

structureReport = verify_project_structure(projectRoot);
assert(structureReport.passed, 'Project structure check failed.');
passCount = passCount + 1;

assert(exist('ga', 'file') == 2, 'MATLAB ga was not found.');
passCount = passCount + 1;

reported = article_reported();
assert(reported.model.hidden_nodes == 2, 'Expected two hidden nodes.');
passCount = passCount + 1;

datasets = synthetic_survival_datasets('NWTCO');
assert(datasets.feature_count == 4 && datasets.patient_count == 309, 'Synthetic NWTCO dimensions mismatch.');
passCount = passCount + 1;

nvars = mlp_weight_count(datasets.feature_count, reported.model.hidden_nodes);
assert(nvars == 2 * datasets.feature_count + 5, 'MLP weight count is wrong.');
passCount = passCount + 1;

weights = zeros(1, nvars);
score = mlp_predict(weights, datasets.X, reported.model.hidden_nodes);
assert(numel(score) == datasets.patient_count, 'Prediction length mismatch.');
passCount = passCount + 1;

[err, details] = c_index_error(-datasets.time, datasets.time, datasets.event);
assert(err >= 0 && err <= 1 && details.permissible_pairs > 0, 'C-index error is invalid.');
passCount = passCount + 1;

split = train_validation_split(datasets, 123, 0.33);
problem = struct();
problem.dataset = split.train;
problem.input_count = split.train.feature_count;
problem.hidden_nodes = reported.model.hidden_nodes;
problem.data_class = split.train.data_class;

gaOptions = optimoptions('ga', ...
    'PopulationSize', 8, ...
    'MaxGenerations', 3, ...
    'EliteCount', 1, ...
    'SelectionFcn', @selectionstochunif, ...
    'CrossoverFcn', @crossoverscattered, ...
    'MutationFcn', @mutationgaussian, ...
    'Display', 'off', ...
    'UseParallel', false);

fitnessFcn = @(x) gnn_fitness(x, problem);
[~, bestFitness, ~, output] = ga(fitnessFcn, nvars, [], [], [], [], [], [], [], gaOptions);
assert(isfinite(bestFitness) && output.funccount > 0, 'MATLAB ga smoke test failed.');
passCount = passCount + 1;

testReport = struct();
testReport.passed = true;
testReport.pass_count = passCount;
testReport.note = 'Minimal MATLAB ga flow tests passed.';
fprintf('Unit tests passed: %d\n', passCount);
end
