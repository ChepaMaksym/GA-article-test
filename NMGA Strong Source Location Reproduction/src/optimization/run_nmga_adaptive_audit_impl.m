function result = run_nmga_adaptive_audit_impl(profile, writeOutputs)
if nargin < 1 || isempty(profile)
    profile = 'quick';
end
if nargin < 2 || isempty(writeOutputs)
    writeOutputs = true;
end

projectRoot = find_project_root();
resultsDir = fullfile(projectRoot, 'sandbox', 'results');
if ~exist(resultsDir, 'dir')
    mkdir(resultsDir);
end

config = audit_profile(profile);
article = article_reported();
auditCases = build_audit_cases(config, article);
convergenceCases = build_convergence_cases(config, article);

caseRows = repmat(empty_case_row(), 1, numel(auditCases) + numel(convergenceCases));
rowIndex = 0;

for i = 1:numel(auditCases)
    observation = build_synthetic_observation(auditCases(i));
    options = nmga_options('NMGA', config.optimizer_profile, config.seed_base + i);
    runResult = run_nmga_optimizer(observation, options, config.generations);
    rowIndex = rowIndex + 1;
    caseRows(rowIndex) = summarize_case(auditCases(i), runResult, 'NMGA');
end

pairRows = repmat(empty_pair_row(), 1, numel(convergenceCases));
for i = 1:numel(convergenceCases)
    observation = build_synthetic_observation(convergenceCases(i));
    seed = config.seed_base + 10000 + i;

    mgaOptions = nmga_options('MGA', config.optimizer_profile, seed);
    nmgaOptions = nmga_options('NMGA', config.optimizer_profile, seed);

    mgaRun = run_mga_optimizer(observation, mgaOptions, config.generations);
    nmgaRun = run_nmga_optimizer(observation, nmgaOptions, config.generations);

    rowIndex = rowIndex + 1;
    caseRows(rowIndex) = summarize_case(convergenceCases(i), nmgaRun, 'NMGA');
    pairRows(i) = summarize_pair(convergenceCases(i), mgaRun, nmgaRun, config.generations);
end

caseRows = caseRows(1:rowIndex);
fidelity = article_fidelity_check(config);
scenarioSummary = summarize_by_class(caseRows);
levelSummary = summarize_by_level(caseRows);
convergenceSummary = summarize_pairs(pairRows);
acceptance = acceptance_checks(caseRows, pairRows, fidelity, config);

result = struct();
result.data_type = 'synthetic_reproduction';
result.profile = profile;
result.config = config;
result.article = article;
result.article_fidelity = fidelity;
result.cases = caseRows;
result.scenario_summary = scenarioSummary;
result.level_summary = levelSummary;
result.convergence_pairs = pairRows;
result.convergence_summary = convergenceSummary;
result.acceptance = acceptance;
result.report_path = fullfile(resultsDir, 'nmga_adaptive_audit_report.md');
result.mat_path = fullfile(resultsDir, 'nmga_adaptive_audit_result.mat');
result.note = ['Audit of article-aligned generation-scheduled NMGA on synthetic observations; ' ...
    'not original article monitoring data.'];

if writeOutputs
    save(result.mat_path, 'result');
    write_audit_report(result);

    fprintf('NMGA adaptive audit report written to: %s\n', result.report_path);
    fprintf('Scenario cases: %d\n', numel(result.cases));
    fprintf('Baseline median position error: %.3f m\n', acceptance.baseline_median_position_error_m);
    fprintf('Article schedule check: Pc monotonic = %d, Pm monotonic = %d\n', ...
        fidelity.pc_monotonic_decrease, fidelity.pm_monotonic_increase);
end
end

function config = audit_profile(profile)
baseOptions = nmga_options('NMGA', profile, 20260511);
switch lower(profile)
    case 'unit'
        casesPerClass = 1;
        optimizerProfile = 'unit';
        baselineThreshold = 25;
    case 'quick'
        casesPerClass = 20;
        optimizerProfile = 'quick';
        baselineThreshold = 15;
    case 'full'
        casesPerClass = 100;
        optimizerProfile = 'full';
        baselineThreshold = 15;
    otherwise
        error('Unknown adaptive audit profile: %s', profile);
end

options = nmga_options('NMGA', optimizerProfile, 20260511);
config = struct();
config.profile = lower(profile);
config.optimizer_profile = optimizerProfile;
config.seed_base = 20260511;
config.cases_per_class = casesPerClass;
config.generations = options.NMGA500Generations;
config.population_size = options.PopulationSize;
config.baseline_position_threshold_m = baselineThreshold;
config.noise_levels = [0, 0.01, 0.05, 0.10, 0.20];
config.sensor_layouts = {'figure_eight_20', 'sparse_10', 'sparse_5', 'sparse_3'};
config.wind_factors = [0.80, 0.90, 1.10, 1.20];
config.source_lb = [-65, -25, 7000, 1.0];
config.source_ub = [10, 55, 22000, 6.0];
config.base_options = baseOptions;
end

function cases = build_audit_cases(config, article)
cases = repmat(empty_case(), 1, 5 * config.cases_per_class);
idx = 0;

for i = 1:config.cases_per_class
    idx = idx + 1;
    source = deterministic_source(i, 11, config);
    cases(idx) = make_case(sprintf('baseline_%03d', i), 'baseline_reconstruction', ...
        'clean', 'figure_eight', source, 0, 1, 1, article);
end

for i = 1:config.cases_per_class
    idx = idx + 1;
    source = deterministic_source(i, 23, config);
    noise = config.noise_levels(1 + mod(i - 1, numel(config.noise_levels)));
    cases(idx) = make_case(sprintf('noise_%03d', i), 'noise_robustness', ...
        sprintf('noise_%02d_percent', round(100 * noise)), 'figure_eight', source, noise, 1, 1, article);
end

for i = 1:config.cases_per_class
    idx = idx + 1;
    source = deterministic_source(i, 37, config);
    cases(idx) = make_case(sprintf('premature_%03d', i), 'premature_convergence_stress', ...
        'symmetric_poor', 'symmetric_poor', source, 0.02, 1, 1, article);
end

for i = 1:config.cases_per_class
    idx = idx + 1;
    source = deterministic_source(i, 41, config);
    layout = config.sensor_layouts{1 + mod(i - 1, numel(config.sensor_layouts))};
    cases(idx) = make_case(sprintf('sensors_%03d', i), 'sensor_sparsity', ...
        layout, layout, source, 0.02, 1, 1, article);
end

for i = 1:config.cases_per_class
    idx = idx + 1;
    source = deterministic_source(i, 53, config);
    windFactor = config.wind_factors(1 + mod(i - 1, numel(config.wind_factors)));
    cases(idx) = make_case(sprintf('wind_%03d', i), 'wind_uncertainty', ...
        sprintf('true_wind_%03d_percent', round(100 * windFactor)), ...
        'figure_eight', source, 0.03, windFactor, 1, article);
end
end

function cases = build_convergence_cases(config, article)
cases = repmat(empty_case(), 1, config.cases_per_class);
for i = 1:config.cases_per_class
    source = deterministic_source(i, 67, config);
    cases(i) = make_case(sprintf('convergence_%03d', i), 'convergence_benchmark', ...
        'mga_vs_nmga_same_budget', 'figure_eight', source, 0.03, 1, 1, article);
end
end

function source = deterministic_source(index, salt, config)
fractions = [unit_fraction(index, salt), unit_fraction(index, salt + 3), ...
    unit_fraction(index, salt + 7), unit_fraction(index, salt + 13)];
source = config.source_lb + fractions .* (config.source_ub - config.source_lb);
end

function value = unit_fraction(index, salt)
value = mod(sin((index + 0.37 * salt) * (12.9898 + salt)) * 43758.5453, 1);
end

function caseData = make_case(name, scenarioClass, level, layout, source, noise, trueWindFactor, modelWindFactor, article)
caseData = empty_case();
caseData.data_type = 'synthetic_reproduction';
caseData.name = name;
caseData.scenario_class = scenarioClass;
caseData.level = level;
caseData.layout = layout;
caseData.true_x_m = source(1);
caseData.true_y_m = source(2);
caseData.true_Q_gps = source(3);
caseData.true_H_m = source(4);
caseData.wind_speed_mps = article.scenario.wind_speed_mps * trueWindFactor;
caseData.model_wind_speed_mps = article.scenario.wind_speed_mps * modelWindFactor;
caseData.stability = article.scenario.stability;
caseData.noise_fraction = noise;
caseData.weight = 1.0;
end

function row = summarize_case(caseData, runResult, method)
history = runResult.history;
row = empty_case_row();
row.name = caseData.name;
row.scenario_class = caseData.scenario_class;
row.level = caseData.level;
row.method = method;
row.layout = caseData.layout;
row.noise_fraction = caseData.noise_fraction;
row.true_wind_speed_mps = caseData.wind_speed_mps;
row.model_wind_speed_mps = caseData.model_wind_speed_mps;
row.true_source = [caseData.true_x_m, caseData.true_y_m, caseData.true_Q_gps, caseData.true_H_m];
row.estimated_source = runResult.best_x;
row.position_error_m = runResult.metrics.position_error_m;
row.x_error_m = runResult.metrics.x_error_m;
row.y_error_m = runResult.metrics.y_error_m;
row.Q_relative_error_percent = runResult.metrics.Q_relative_error_percent;
row.H_relative_error_percent = runResult.metrics.H_relative_error_percent;
row.best_objective = runResult.best_objective;
row.initial_best_objective = runResult.initial_best_objective;
row.objective_improvement_ratio = runResult.initial_best_objective ./ max(runResult.best_objective, eps);
row.generation_to_best = runResult.generation_to_best;
row.runtime_seconds = runResult.runtime_seconds;
row.generations = runResult.generations;
row.seed = runResult.options.Seed;
row.pc_start = history.crossoverRate(1);
row.pc_end = history.crossoverRate(end);
row.pm_start = history.mutationRate(1);
row.pm_end = history.mutationRate(end);
row.diversity_start = history.populationDiversity(1);
row.diversity_end = history.populationDiversity(end);
row.diversity_min = min(history.populationDiversity);
row.max_stagnation_count = max(history.stagnationCount);
end

function row = summarize_pair(caseData, mgaRun, nmgaRun, generations)
row = empty_pair_row();
row.name = caseData.name;
row.seed = mgaRun.options.Seed;
row.generations = generations;
row.same_budget = mgaRun.generations == nmgaRun.generations;
row.same_seed = mgaRun.options.Seed == nmgaRun.options.Seed;
row.mga_position_error_m = mgaRun.metrics.position_error_m;
row.nmga_position_error_m = nmgaRun.metrics.position_error_m;
row.mga_generation_to_best = mgaRun.generation_to_best;
row.nmga_generation_to_best = nmgaRun.generation_to_best;
row.mga_runtime_seconds = mgaRun.runtime_seconds;
row.nmga_runtime_seconds = nmgaRun.runtime_seconds;
row.mga_best_objective = mgaRun.best_objective;
row.nmga_best_objective = nmgaRun.best_objective;
end

function fidelity = article_fidelity_check(config)
options = nmga_options('NMGA', config.optimizer_profile, config.seed_base);
pc = zeros(config.generations, 1);
pm = zeros(config.generations, 1);
for generation = 1:config.generations
    [pc(generation), pm(generation)] = nmga_adaptive_rates(generation, config.generations, options);
end

fidelity = struct();
fidelity.control_type = 'generation-scheduled parameter control';
fidelity.feedback_adaptive = false;
fidelity.mutation_increase_reason = 'Pm is a function of generation/maxGenerations; diversity and stagnation are logged but not used by nmga_adaptive_rates.';
fidelity.pc_start = pc(1);
fidelity.pc_end = pc(end);
fidelity.pm_start = pm(1);
fidelity.pm_end = pm(end);
fidelity.pc_monotonic_decrease = all(diff(pc) <= 1.0e-12);
fidelity.pm_monotonic_increase = all(diff(pm) >= -1.0e-12);
fidelity.pc_within_bounds = min(pc) >= options.NMGACrossoverMin - 1.0e-12 && max(pc) <= options.NMGACrossoverMax + 1.0e-12;
fidelity.pm_within_bounds = min(pm) >= options.NMGAMutationMin - 1.0e-12 && max(pm) <= options.NMGAMutationMax + 1.0e-12;
end

function summaries = summarize_by_class(rows)
classes = unique({rows.scenario_class}, 'stable');
summaries = repmat(empty_summary_row(), 1, numel(classes));
for i = 1:numel(classes)
    idx = strcmp({rows.scenario_class}, classes{i});
    summaries(i) = summarize_rows(classes{i}, 'all', rows(idx));
end
end

function summaries = summarize_by_level(rows)
keys = {};
for i = 1:numel(rows)
    keys{end + 1} = [rows(i).scenario_class, '::', rows(i).level]; %#ok<AGROW>
end
keys = unique(keys, 'stable');
summaries = repmat(empty_summary_row(), 1, numel(keys));
for i = 1:numel(keys)
    parts = split_key(keys{i});
    idx = strcmp({rows.scenario_class}, parts{1}) & strcmp({rows.level}, parts{2});
    summaries(i) = summarize_rows(parts{1}, parts{2}, rows(idx));
end
end

function parts = split_key(key)
marker = strfind(key, '::');
parts = {key(1:marker - 1), key(marker + 2:end)};
end

function summary = summarize_rows(scenarioClass, level, rows)
positionErrors = [rows.position_error_m];
qErrors = [rows.Q_relative_error_percent];
hErrors = [rows.H_relative_error_percent];
summary = empty_summary_row();
summary.scenario_class = scenarioClass;
summary.level = level;
summary.count = numel(rows);
summary.mean_position_error_m = mean(positionErrors);
summary.median_position_error_m = median(positionErrors);
summary.worst_position_error_m = max(positionErrors);
summary.mean_Q_relative_error_percent = mean(qErrors);
summary.mean_H_relative_error_percent = mean(hErrors);
summary.mean_generation_to_best = mean([rows.generation_to_best]);
summary.mean_runtime_seconds = mean([rows.runtime_seconds]);
summary.mean_diversity_start = mean([rows.diversity_start]);
summary.mean_diversity_end = mean([rows.diversity_end]);
summary.max_stagnation_count = max([rows.max_stagnation_count]);
end

function summary = summarize_pairs(rows)
summary = struct();
summary.count = numel(rows);
summary.same_budget_all = all([rows.same_budget]);
summary.same_seed_all = all([rows.same_seed]);
summary.mean_mga_position_error_m = mean([rows.mga_position_error_m]);
summary.mean_nmga_position_error_m = mean([rows.nmga_position_error_m]);
summary.median_mga_position_error_m = median([rows.mga_position_error_m]);
summary.median_nmga_position_error_m = median([rows.nmga_position_error_m]);
summary.mean_mga_generation_to_best = mean([rows.mga_generation_to_best]);
summary.mean_nmga_generation_to_best = mean([rows.nmga_generation_to_best]);
summary.mean_mga_runtime_seconds = mean([rows.mga_runtime_seconds]);
summary.mean_nmga_runtime_seconds = mean([rows.nmga_runtime_seconds]);
end

function acceptance = acceptance_checks(caseRows, pairRows, fidelity, config)
baselineRows = caseRows(strcmp({caseRows.scenario_class}, 'baseline_reconstruction'));
baselineErrors = [baselineRows.position_error_m];
historyFinite = all(isfinite([caseRows.diversity_start])) ...
    && all(isfinite([caseRows.diversity_end])) ...
    && all(isfinite([caseRows.max_stagnation_count]));

acceptance = struct();
acceptance.baseline_median_position_error_m = median(baselineErrors);
acceptance.baseline_position_threshold_m = config.baseline_position_threshold_m;
acceptance.baseline_passed = acceptance.baseline_median_position_error_m <= config.baseline_position_threshold_m;
acceptance.rate_schedule_passed = fidelity.pc_monotonic_decrease && fidelity.pm_monotonic_increase ...
    && fidelity.pc_within_bounds && fidelity.pm_within_bounds;
acceptance.history_metrics_finite = historyFinite;
acceptance.same_budget_convergence_pairs = all([pairRows.same_budget]);
acceptance.same_seed_convergence_pairs = all([pairRows.same_seed]);
acceptance.feedback_adaptive_claim = false;
acceptance.population_collapse_rescue_claim = 'Not claimed: current NMGA raises mutation by generation schedule, not diversity feedback.';
end

function write_audit_report(result)
fid = fopen(result.report_path, 'w');
if fid == -1
    error('Cannot open audit report for writing: %s', result.report_path);
end
cleanupObj = onCleanup(@() fclose(fid)); %#ok<NASGU>

fprintf(fid, '# NMGA Adaptive Audit Report\n\n');
fprintf(fid, 'Generated by `run_nmga_adaptive_audit.m` with profile `%s`.\n\n', result.profile);
fprintf(fid, '## Scope\n');
fprintf(fid, 'This audit checks the article-aligned NMGA as implemented. It does not replace it with feedback-adaptive control.\n\n');
fprintf(fid, '- Data type: `%s`\n', result.data_type);
fprintf(fid, '- Cases per scenario class: `%d`\n', result.config.cases_per_class);
fprintf(fid, '- Population size: `%d`\n', result.config.population_size);
fprintf(fid, '- Generations per audit run: `%d`\n', result.config.generations);
fprintf(fid, '- Dynamic source tracking: out of scope for v1 because the chromosome is static `[x, y, Q, H]`.\n\n');

fprintf(fid, '## Article Fidelity And Adaptive Control\n');
fprintf(fid, '- Control type: `%s`\n', result.article_fidelity.control_type);
fprintf(fid, '- Feedback-adaptive: `%d`\n', result.article_fidelity.feedback_adaptive);
fprintf(fid, '- Pc start/end: `%.6f` -> `%.6f`\n', result.article_fidelity.pc_start, result.article_fidelity.pc_end);
fprintf(fid, '- Pm start/end: `%.6f` -> `%.6f`\n', result.article_fidelity.pm_start, result.article_fidelity.pm_end);
fprintf(fid, '- Pc monotonic decrease: `%d`\n', result.article_fidelity.pc_monotonic_decrease);
fprintf(fid, '- Pm monotonic increase: `%d`\n', result.article_fidelity.pm_monotonic_increase);
fprintf(fid, '- Mutation increase reason: %s\n\n', result.article_fidelity.mutation_increase_reason);

fprintf(fid, '## Acceptance Checks\n');
fprintf(fid, '| Check | Result |\n');
fprintf(fid, '|---|---:|\n');
fprintf(fid, '| Baseline median position error <= %.2f m | %d |\n', ...
    result.acceptance.baseline_position_threshold_m, result.acceptance.baseline_passed);
fprintf(fid, '| Rate schedule monotonic and within bounds | %d |\n', result.acceptance.rate_schedule_passed);
fprintf(fid, '| Diversity/stagnation metrics finite | %d |\n', result.acceptance.history_metrics_finite);
fprintf(fid, '| MGA/NMGA convergence pairs use same budget | %d |\n', result.acceptance.same_budget_convergence_pairs);
fprintf(fid, '| MGA/NMGA convergence pairs use same seed | %d |\n\n', result.acceptance.same_seed_convergence_pairs);
fprintf(fid, '%s\n\n', result.acceptance.population_collapse_rescue_claim);

fprintf(fid, '## Scenario Summary\n');
fprintf(fid, '| Scenario | Count | Median position err m | Mean position err m | Worst position err m | Mean Q err %% | Mean H err %% | Mean gen to best | Mean runtime s | Diversity start -> end | Max stagnation |\n');
fprintf(fid, '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n');
for i = 1:numel(result.scenario_summary)
    row = result.scenario_summary(i);
    fprintf(fid, '| %s | %d | %.3f | %.3f | %.3f | %.3f | %.3f | %.2f | %.3f | %.4f -> %.4f | %.0f |\n', ...
        row.scenario_class, row.count, row.median_position_error_m, row.mean_position_error_m, ...
        row.worst_position_error_m, row.mean_Q_relative_error_percent, row.mean_H_relative_error_percent, ...
        row.mean_generation_to_best, row.mean_runtime_seconds, row.mean_diversity_start, row.mean_diversity_end, ...
        row.max_stagnation_count);
end

fprintf(fid, '\n## Level Breakdown\n');
fprintf(fid, '| Scenario | Level | Count | Median position err m | Worst position err m | Mean gen to best |\n');
fprintf(fid, '|---|---|---:|---:|---:|---:|\n');
for i = 1:numel(result.level_summary)
    row = result.level_summary(i);
    if ismember(row.scenario_class, {'noise_robustness', 'sensor_sparsity', 'wind_uncertainty'})
        fprintf(fid, '| %s | %s | %d | %.3f | %.3f | %.2f |\n', ...
            row.scenario_class, row.level, row.count, row.median_position_error_m, ...
            row.worst_position_error_m, row.mean_generation_to_best);
    end
end

fprintf(fid, '\n## Convergence Benchmark: MGA vs NMGA Same Budget\n');
fprintf(fid, '| Metric | MGA | NMGA |\n');
fprintf(fid, '|---|---:|---:|\n');
fprintf(fid, '| Mean position error m | %.3f | %.3f |\n', ...
    result.convergence_summary.mean_mga_position_error_m, result.convergence_summary.mean_nmga_position_error_m);
fprintf(fid, '| Median position error m | %.3f | %.3f |\n', ...
    result.convergence_summary.median_mga_position_error_m, result.convergence_summary.median_nmga_position_error_m);
fprintf(fid, '| Mean generation to best | %.2f | %.2f |\n', ...
    result.convergence_summary.mean_mga_generation_to_best, result.convergence_summary.mean_nmga_generation_to_best);
fprintf(fid, '| Mean runtime seconds | %.3f | %.3f |\n\n', ...
    result.convergence_summary.mean_mga_runtime_seconds, result.convergence_summary.mean_nmga_runtime_seconds);

fprintf(fid, '## Limitations\n');
fprintf(fid, '- Raw article monitoring data and exact sensor coordinates are unavailable; all audit cases are `synthetic_reproduction`.\n');
fprintf(fid, '- Noise, sparse sensor, wind uncertainty, and premature convergence scenarios are stress tests, not article claims.\n');
fprintf(fid, '- The current NMGA logs diversity and stagnation, but `nmga_adaptive_rates` does not use them to change `Pc` or `Pm`.\n');
end

function caseData = empty_case()
caseData = struct( ...
    'data_type', '', ...
    'name', '', ...
    'scenario_class', '', ...
    'level', '', ...
    'layout', '', ...
    'true_x_m', NaN, ...
    'true_y_m', NaN, ...
    'true_Q_gps', NaN, ...
    'true_H_m', NaN, ...
    'wind_speed_mps', NaN, ...
    'model_wind_speed_mps', NaN, ...
    'stability', '', ...
    'noise_fraction', NaN, ...
    'weight', NaN);
end

function row = empty_case_row()
row = struct( ...
    'name', '', ...
    'scenario_class', '', ...
    'level', '', ...
    'method', '', ...
    'layout', '', ...
    'noise_fraction', NaN, ...
    'true_wind_speed_mps', NaN, ...
    'model_wind_speed_mps', NaN, ...
    'true_source', [NaN, NaN, NaN, NaN], ...
    'estimated_source', [NaN, NaN, NaN, NaN], ...
    'position_error_m', NaN, ...
    'x_error_m', NaN, ...
    'y_error_m', NaN, ...
    'Q_relative_error_percent', NaN, ...
    'H_relative_error_percent', NaN, ...
    'best_objective', NaN, ...
    'initial_best_objective', NaN, ...
    'objective_improvement_ratio', NaN, ...
    'generation_to_best', NaN, ...
    'runtime_seconds', NaN, ...
    'generations', NaN, ...
    'seed', NaN, ...
    'pc_start', NaN, ...
    'pc_end', NaN, ...
    'pm_start', NaN, ...
    'pm_end', NaN, ...
    'diversity_start', NaN, ...
    'diversity_end', NaN, ...
    'diversity_min', NaN, ...
    'max_stagnation_count', NaN);
end

function row = empty_pair_row()
row = struct( ...
    'name', '', ...
    'seed', NaN, ...
    'generations', NaN, ...
    'same_budget', false, ...
    'same_seed', false, ...
    'mga_position_error_m', NaN, ...
    'nmga_position_error_m', NaN, ...
    'mga_generation_to_best', NaN, ...
    'nmga_generation_to_best', NaN, ...
    'mga_runtime_seconds', NaN, ...
    'nmga_runtime_seconds', NaN, ...
    'mga_best_objective', NaN, ...
    'nmga_best_objective', NaN);
end

function row = empty_summary_row()
row = struct( ...
    'scenario_class', '', ...
    'level', '', ...
    'count', NaN, ...
    'mean_position_error_m', NaN, ...
    'median_position_error_m', NaN, ...
    'worst_position_error_m', NaN, ...
    'mean_Q_relative_error_percent', NaN, ...
    'mean_H_relative_error_percent', NaN, ...
    'mean_generation_to_best', NaN, ...
    'mean_runtime_seconds', NaN, ...
    'mean_diversity_start', NaN, ...
    'mean_diversity_end', NaN, ...
    'max_stagnation_count', NaN);
end

function projectRoot = find_project_root()
currentDir = fileparts(mfilename('fullpath'));
projectRoot = currentDir;
while ~isfile(fullfile(projectRoot, 'main.m'))
    parentDir = fileparts(projectRoot);
    if strcmp(parentDir, projectRoot)
        error('Project root with main.m was not found.');
    end
    projectRoot = parentDir;
end
end
