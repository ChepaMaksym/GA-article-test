projectRoot = fileparts(mfilename('fullpath'));
addpath(genpath(fullfile(projectRoot, 'src')));

% MAIN FLOW: MATLAB GA only.
% 1. Load source metadata and synthetic survival datasets.
% 2. Split each dataset into train/validation data.
% 3. Configure MATLAB Global Optimization Toolbox ga.
% 4. Train MLP weights with ga.
% 5. Validate by c-index error and write one report.

assert(exist('ga', 'file') == 2, ...
    'Global Optimization Toolbox is required because the main flow uses MATLAB ga.');

article = article_metadata();
reported = article_reported();
datasets = synthetic_survival_datasets();
seeds = [20260503, 20260504];

resultsDir = fullfile(projectRoot, 'sandbox', 'results');
if exist(resultsDir, 'dir') ~= 7
    mkdir(resultsDir);
end

runs = repmat(empty_run(), 1, numel(datasets) * numel(seeds));
runIndex = 1;

for datasetIndex = 1:numel(datasets)
    for seedIndex = 1:numel(seeds)
        seed = seeds(seedIndex);
        rng(seed, 'twister');

        split = train_validation_split(datasets(datasetIndex), seed, 0.33);
        trainProblem = make_problem(split.train, reported);
        validationProblem = make_problem(split.validation, reported);
        nvars = mlp_weight_count(trainProblem.input_count, trainProblem.hidden_nodes);

        gaOptions = optimoptions('ga', ...
            'PopulationSize', 36, ...
            'MaxGenerations', 35, ...
            'EliteCount', 2, ...
            'SelectionFcn', @selectionstochunif, ...
            'CrossoverFcn', @crossoverscattered, ...
            'MutationFcn', @mutationgaussian, ...
            'Display', 'off', ...
            'UseParallel', false);

        fitnessFcn = @(weights) gnn_fitness(weights, trainProblem);
        [bestWeights, trainError, exitflag, output] = ga( ...
            fitnessFcn, nvars, [], [], [], [], [], [], [], gaOptions);

        [validationError, validationDetails] = gnn_fitness(bestWeights, validationProblem);
        runs(runIndex) = make_run(datasets(datasetIndex).name, seed, trainError, ...
            validationError, validationDetails.c_index, output.funccount, exitflag);
        runIndex = runIndex + 1;
    end
end

summary = summarize_runs(runs);
result = struct();
result.article = article;
result.reported = reported;
result.matlab_ga.selection = 'selectionstochunif';
result.matlab_ga.crossover = 'crossoverscattered';
result.matlab_ga.mutation = 'mutationgaussian';
result.runs = runs;
result.summary = summary;
result.report_path = fullfile(resultsDir, 'matlab_ga_report.md');
result.mat_path = fullfile(resultsDir, 'matlab_ga_result.mat');

save(result.mat_path, 'result');
write_report(result);

fprintf('Source: %s\n', article.title);
fprintf('Main flow: MATLAB ga -> MLP weights -> c-index validation\n');
fprintf('Runs: %d\n', numel(runs));
fprintf('Mean validation c-index error: %.4f\n', summary.mean_validation_error);
fprintf('Mean validation c-index: %.4f\n', summary.mean_validation_c_index);
fprintf('Report: %s\n', result.report_path);

function problem = make_problem(dataset, reported)
problem = struct();
problem.dataset = dataset;
problem.input_count = dataset.feature_count;
problem.hidden_nodes = reported.model.hidden_nodes;
problem.data_class = dataset.data_class;
end

function run = empty_run()
run = struct();
run.dataset = '';
run.seed = [];
run.train_error = [];
run.validation_error = [];
run.validation_c_index = [];
run.function_evaluations = [];
run.exitflag = [];
end

function run = make_run(datasetName, seed, trainError, validationError, validationCIndex, functionEvaluations, exitflag)
run = empty_run();
run.dataset = datasetName;
run.seed = seed;
run.train_error = trainError;
run.validation_error = validationError;
run.validation_c_index = validationCIndex;
run.function_evaluations = functionEvaluations;
run.exitflag = exitflag;
end

function summary = summarize_runs(runs)
summary = struct();
summary.run_count = numel(runs);
summary.mean_train_error = mean([runs.train_error]);
summary.mean_validation_error = mean([runs.validation_error]);
summary.mean_validation_c_index = mean([runs.validation_c_index]);
summary.mean_function_evaluations = mean([runs.function_evaluations]);
end

function write_report(result)
fid = fopen(result.report_path, 'w');
if fid == -1
    error('Cannot open report: %s', result.report_path);
end
cleanupObj = onCleanup(@() fclose(fid)); %#ok<NASGU>

fprintf(fid, '# MATLAB GA Main Flow Report\n\n');
fprintf(fid, '## Source\n');
fprintf(fid, '- Title: %s\n', result.article.title);
fprintf(fid, '- Author: %s\n', result.article.author);
fprintf(fid, '- Local PDF: `%s`\n\n', result.article.source_pdf);

fprintf(fid, '## Main Flow\n');
fprintf(fid, '1. `synthetic_survival_datasets`\n');
fprintf(fid, '2. `train_validation_split`\n');
fprintf(fid, '3. `optimoptions(''ga'')`\n');
fprintf(fid, '4. `ga(...)`\n');
fprintf(fid, '5. `gnn_fitness -> mlp_predict -> c_index_error`\n\n');

fprintf(fid, '## MATLAB GA Methods\n');
fprintf(fid, '- Selection: `%s`\n', result.matlab_ga.selection);
fprintf(fid, '- Crossover: `%s`\n', result.matlab_ga.crossover);
fprintf(fid, '- Mutation: `%s`\n\n', result.matlab_ga.mutation);

fprintf(fid, '## Summary\n');
fprintf(fid, '- Runs: %d\n', result.summary.run_count);
fprintf(fid, '- Mean train c-index error: %.4f\n', result.summary.mean_train_error);
fprintf(fid, '- Mean validation c-index error: %.4f\n', result.summary.mean_validation_error);
fprintf(fid, '- Mean validation c-index: %.4f\n', result.summary.mean_validation_c_index);
fprintf(fid, '- Mean function evaluations: %.1f\n\n', result.summary.mean_function_evaluations);

fprintf(fid, '| Dataset | Seed | Train error | Validation error | Validation c-index | Function evals | Exitflag |\n');
fprintf(fid, '|---|---:|---:|---:|---:|---:|---:|\n');
for i = 1:numel(result.runs)
    row = result.runs(i);
    fprintf(fid, '| %s | %d | %.4f | %.4f | %.4f | %d | %d |\n', ...
        row.dataset, row.seed, row.train_error, row.validation_error, ...
        row.validation_c_index, row.function_evaluations, row.exitflag);
end
end
