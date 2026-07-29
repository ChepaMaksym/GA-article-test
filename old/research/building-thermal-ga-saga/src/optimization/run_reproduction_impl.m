function reproduction = run_reproduction_impl()
projectRoot = find_project_root();
resultsDir = fullfile(projectRoot, 'sandbox', 'results');
if exist(resultsDir, 'dir') ~= 7
    mkdir(resultsDir);
end

article = article_metadata();
reported = article_reported();
cases = building_cases();
scenarios = synthetic_sandbox_scenarios();
scenario = scenarios(1);
seeds = [20260503, 20260504, 20260505];

runs = repmat(empty_reproduction_run(), 1, numel(cases) * 2 * numel(seeds));
idx = 1;
for c = 1:numel(cases)
    for coolingMode = 1:2
        noCooling = coolingMode == 2;
        for s = 1:numel(seeds)
            [gaOptions, sagaOptions] = configure_options_for_scenario(seeds(s), scenario);
            problem = building_problem(cases(c), noCooling, scenario);
            gaResult = run_classical_ga(problem, gaOptions);
            sagaResult = run_saga_optimizer(problem, sagaOptions);
            criterion = satisfies_saga_criterion(sagaResult);

            runs(idx) = make_reproduction_run(cases(c), noCooling, seeds(s), gaResult, sagaResult, criterion);
            idx = idx + 1;
        end
    end
end

summary = compare_ga_saga_runs(runs);
classification = classify_article_sga();

reproduction = struct();
reproduction.article = article;
reproduction.reported = reported;
reproduction.article_sga_classification = classification;
reproduction.runs = runs;
reproduction.summary = summary;
reproduction.report_path = fullfile(resultsDir, 'reproduction_report.md');
reproduction.mat_path = fullfile(resultsDir, 'reproduction_result.mat');

save(reproduction.mat_path, 'reproduction');
write_reproduction_report(reproduction);

fprintf('Reproduction report written to: %s\n', reproduction.report_path);
fprintf('Reproduction MAT written to: %s\n', reproduction.mat_path);
end

function run = empty_reproduction_run()
run = struct();
run.case_id = [];
run.case_label = '';
run.no_cooling = false;
run.seed = [];
run.ga_lcc_eur = [];
run.saga_lcc_eur = [];
run.ga_best_objective = [];
run.saga_best_objective = [];
run.ga_function_evaluations = [];
run.saga_function_evaluations = [];
run.saga_criterion_passed = false;
run.saga_criterion_message = '';
run.ga_result = [];
run.saga_result = [];
end

function run = make_reproduction_run(caseDef, noCooling, seed, gaResult, sagaResult, criterion)
run = empty_reproduction_run();
run.case_id = caseDef.id;
run.case_label = caseDef.label;
run.no_cooling = noCooling;
run.seed = seed;
run.ga_lcc_eur = gaResult.best_lcc_eur;
run.saga_lcc_eur = sagaResult.best_lcc_eur;
run.ga_best_objective = gaResult.best_objective;
run.saga_best_objective = sagaResult.best_objective;
run.ga_function_evaluations = gaResult.function_evaluations;
run.saga_function_evaluations = sagaResult.function_evaluations;
run.saga_criterion_passed = criterion.passed;
run.saga_criterion_message = criterion.message;
run.ga_result = gaResult;
run.saga_result = sagaResult;
end

function write_reproduction_report(reproduction)
fid = fopen(reproduction.report_path, 'w');
if fid == -1
    error('Cannot open reproduction report: %s', reproduction.report_path);
end
cleanupObj = onCleanup(@() fclose(fid)); %#ok<NASGU>

fprintf(fid, '# GA vs Formal SAGA Reproduction Report\n\n');
fprintf(fid, '## Article\n');
fprintf(fid, '- Title: %s\n', reproduction.article.title);
fprintf(fid, '- Authors: %s\n', strjoin(reproduction.article.authors, ', '));
fprintf(fid, '- DOI: `%s`\n', reproduction.article.doi);
fprintf(fid, '- URL: %s\n\n', reproduction.article.url);

fprintf(fid, '## Scope\n');
fprintf(fid, 'This is a synthetic surrogate reproduction because the article page does not bundle the EnergyPlus model or source MATLAB code. ');
fprintf(fid, 'The fuzzy SGA from the article is classified as `%s` under the local formal SAGA plan.\n\n', ...
    reproduction.article_sga_classification.local_plan_class);
fprintf(fid, 'Classification reason: %s\n\n', reproduction.article_sga_classification.reason);

fprintf(fid, '## Summary\n');
fprintf(fid, '- Runs: %d\n', reproduction.summary.run_count);
fprintf(fid, '- Mean classical GA LCC: %.3f EUR\n', reproduction.summary.mean_ga_lcc);
fprintf(fid, '- Mean formal SAGA LCC: %.3f EUR\n', reproduction.summary.mean_saga_lcc);
fprintf(fid, '- Mean SAGA minus GA delta: %.3f%%\n', reproduction.summary.mean_delta_percent);
fprintf(fid, '- SAGA win rate: %.3f\n', reproduction.summary.saga_win_rate);
fprintf(fid, '- All SAGA criteria passed: %d\n\n', reproduction.summary.all_saga_criteria_passed);

fprintf(fid, '## Run Table\n');
fprintf(fid, '| Case | Mode | Seed | GA LCC EUR | SAGA LCC EUR | GA evals | SAGA evals | SAGA criterion |\n');
fprintf(fid, '|---:|---|---:|---:|---:|---:|---:|---|\n');
for i = 1:numel(reproduction.runs)
    row = reproduction.runs(i);
    mode = 'cooling';
    if row.no_cooling
        mode = 'no_cooling';
    end
    criterion = 'PASS';
    if ~row.saga_criterion_passed
        criterion = 'FAIL';
    end
    fprintf(fid, '| %d | %s | %d | %.3f | %.3f | %d | %d | %s |\n', ...
        row.case_id, mode, row.seed, row.ga_lcc_eur, row.saga_lcc_eur, ...
        row.ga_function_evaluations, row.saga_function_evaluations, criterion);
end

fprintf(fid, '\n## Reported Article Savings Context\n');
fprintf(fid, 'Cooling cases, LCC savings percent: [%s]\n\n', number_list(reproduction.reported.cooling_lcc_savings_percent));
fprintf(fid, 'No-cooling cases, LCC savings percent: [%s]\n', number_list(reproduction.reported.no_cooling_lcc_savings_percent));
end

function text = number_list(values)
parts = cell(1, numel(values));
for i = 1:numel(values)
    parts{i} = sprintf('%.1f', values(i));
end
text = strjoin(parts, ', ');
end

function projectRoot = find_project_root()
currentDir = fileparts(mfilename('fullpath'));
projectRoot = currentDir;
while exist(fullfile(projectRoot, 'main.m'), 'file') ~= 2
    parentDir = fileparts(projectRoot);
    if strcmp(parentDir, projectRoot)
        error('Project root with main.m was not found.');
    end
    projectRoot = parentDir;
end
end
