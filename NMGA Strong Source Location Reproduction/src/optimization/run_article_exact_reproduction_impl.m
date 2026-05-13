function result = run_article_exact_reproduction_impl(profile)
if nargin < 1 || isempty(profile)
    profile = 'article_exact';
end

projectRoot = find_project_root();
resultsDir = fullfile(projectRoot, 'sandbox', 'results');
if ~exist(resultsDir, 'dir')
    mkdir(resultsDir);
end

spec = article_exact_spec();
article = article_reported();
caseData = synthetic_source_cases('reproduction');
observation = build_synthetic_observation(caseData);
observation.data_type = 'synthetic_reproduction';
observation.objective_mode = spec.objective.mode;
observation.note = ['Synthetic observation for public-text exact MGA/NMGA operator replication; ', ...
    'not original article_raw monitoring data.'];

baseOptions = article_profile_options('NMGA', profile, 20260428, spec);

protocols = [ ...
    protocol_row('mga', 'MGA', baseOptions.MGAGenerations, 20260428); ...
    protocol_row('nmga_1000', 'NMGA', baseOptions.NMGA1000Generations, 20261428); ...
    protocol_row('nmga_500', 'NMGA', baseOptions.NMGA500Generations, 20262428)];

for p = 1:numel(protocols)
    protocols(p).runs = repmat(empty_run_result(), 1, baseOptions.RepeatCount);
    for i = 1:baseOptions.RepeatCount
        options = article_profile_options(protocols(p).method, profile, protocols(p).seed_base + i, spec);
        if strcmpi(protocols(p).method, 'MGA')
            runResult = run_mga_optimizer(observation, options, protocols(p).generations);
        else
            runResult = run_nmga_optimizer(observation, options, protocols(p).generations);
        end
        protocols(p).runs(i) = summarize_run(runResult);
    end
    protocols(p).metrics = aggregate_runs(protocols(p).runs, observation.true_source);
    protocols(p).convergence = collect_histories(protocols(p).runs);
    protocols(p).absolute_errors = collect_absolute_errors(protocols(p).runs, observation.true_source);
end

result = struct();
result.spec = spec;
result.article = article;
result.profile = lower(profile);
result.repeat_count = baseOptions.RepeatCount;
result.population_size = baseOptions.PopulationSize;
result.data_type = observation.data_type;
result.data_provenance = 'synthetic_reproduction';
result.raw_exact_status = 'blocked_without_article_raw_sensor_coordinates_and_observed_concentrations';
result.objective_mode = spec.objective.mode;
result.operator_mode = 'article_exact';
result.observation = observation;
result.protocols = protocols;
result.article_table1_comparison = compare_against_table1(protocols, spec.table1);
result.report_path = fullfile(resultsDir, 'article_exact_report.md');
result.operator_audit_path = fullfile(resultsDir, 'operator_audit_report.md');
result.mat_path = fullfile(resultsDir, 'article_exact_result.mat');
result.note = ['Default profile article_exact runs the public-text Table 1 protocol. ', ...
    'Profiles quick/unit are smoke variants that keep article operators but reduce cost.'];

write_article_exact_report(result);
write_operator_audit_report(result);
save(result.mat_path, 'result');

fprintf('Article exact report written to: %s\n', result.report_path);
fprintf('Operator audit report written to: %s\n', result.operator_audit_path);
fprintf('Data provenance: %s; raw exact status: %s\n', result.data_provenance, result.raw_exact_status);
end

function options = article_profile_options(method, profile, seed, spec)
profile = lower(profile);
switch profile
    case 'article_exact'
        options = nmga_options(method, 'article_exact', seed);
    case {'quick', 'unit'}
        options = nmga_options(method, profile, seed);
        options.ObjectiveMode = spec.objective.mode;
        options.OperatorMode = 'article_exact';
        options.ArticleExact = true;
    otherwise
        error('Unknown article exact reproduction profile: %s', profile);
end
options.Method = upper(method);
end

function protocol = protocol_row(key, method, generations, seedBase)
protocol = struct();
protocol.key = key;
protocol.method = method;
protocol.generations = generations;
protocol.seed_base = seedBase;
protocol.runs = [];
protocol.metrics = [];
protocol.convergence = [];
protocol.absolute_errors = [];
end

function row = summarize_run(runResult)
row = empty_run_result();
row.method = runResult.method;
row.generations = runResult.generations;
row.seed = runResult.options.Seed;
row.best_objective = runResult.best_objective;
row.initial_best_objective = runResult.initial_best_objective;
row.best_x = runResult.best_x;
row.position_error_m = runResult.metrics.position_error_m;
row.x_error_m = runResult.metrics.x_error_m;
row.y_error_m = runResult.metrics.y_error_m;
row.Q_error_gps = runResult.metrics.Q_error_gps;
row.Q_relative_error_percent = runResult.metrics.Q_relative_error_percent;
row.H_error_m = runResult.metrics.H_error_m;
row.H_relative_error_percent = runResult.metrics.H_relative_error_percent;
row.generation_to_best = runResult.generation_to_best;
row.runtime_seconds = runResult.runtime_seconds;
row.best_objective_history = runResult.history.bestObjective;
row.mean_objective_history = runResult.history.meanObjective;
row.crossover_rate_history = runResult.history.crossoverRate;
row.mutation_rate_history = runResult.history.mutationRate;
end

function aggregate = aggregate_runs(runs, trueSource)
estimates = vertcat(runs.best_x);
aggregate = struct();
aggregate.count = numel(runs);
aggregate.mean_x_m = mean(estimates(:, 1));
aggregate.std_x_m = std(estimates(:, 1));
aggregate.relative_error_x_percent = relative_error_percent(aggregate.mean_x_m, trueSource(1));
aggregate.mean_y_m = mean(estimates(:, 2));
aggregate.std_y_m = std(estimates(:, 2));
aggregate.relative_error_y_percent = relative_error_percent(aggregate.mean_y_m, trueSource(2));
aggregate.mean_Q_gps = mean(estimates(:, 3));
aggregate.std_Q_gps = std(estimates(:, 3));
aggregate.relative_error_Q_percent = relative_error_percent(aggregate.mean_Q_gps, trueSource(3));
aggregate.mean_H_m = mean(estimates(:, 4));
aggregate.std_H_m = std(estimates(:, 4));
aggregate.relative_error_H_percent = relative_error_percent(aggregate.mean_H_m, trueSource(4));
aggregate.mean_position_error_m = mean([runs.position_error_m]);
aggregate.std_position_error_m = std([runs.position_error_m]);
aggregate.mean_best_objective = mean([runs.best_objective]);
aggregate.std_best_objective = std([runs.best_objective]);
aggregate.mean_generation_to_best = mean([runs.generation_to_best]);
aggregate.mean_runtime_seconds = mean([runs.runtime_seconds]);
end

function value = relative_error_percent(estimate, truth)
value = 100 * abs(estimate - truth) / max(abs(truth), eps);
end

function histories = collect_histories(runs)
maxGenerations = max([runs.generations]);
count = numel(runs);
histories = struct();
histories.best_objective = NaN(maxGenerations, count);
histories.mean_objective = NaN(maxGenerations, count);
histories.crossover_rate = NaN(maxGenerations, count);
histories.mutation_rate = NaN(maxGenerations, count);
for i = 1:count
    n = numel(runs(i).best_objective_history);
    histories.best_objective(1:n, i) = runs(i).best_objective_history(:);
    histories.mean_objective(1:n, i) = runs(i).mean_objective_history(:);
    histories.crossover_rate(1:n, i) = runs(i).crossover_rate_history(:);
    histories.mutation_rate(1:n, i) = runs(i).mutation_rate_history(:);
end
end

function errors = collect_absolute_errors(runs, trueSource)
estimates = vertcat(runs.best_x);
errors = abs(estimates - trueSource);
end

function comparison = compare_against_table1(protocols, table1)
comparison = repmat(struct( ...
    'key', '', ...
    'local_method', '', ...
    'article_setup', '', ...
    'delta_mean_x_m', NaN, ...
    'delta_mean_y_m', NaN, ...
    'delta_mean_Q_gps', NaN, ...
    'delta_mean_H_m', NaN), 1, numel(protocols));

for i = 1:numel(protocols)
    articleRow = table1(i);
    metrics = protocols(i).metrics;
    comparison(i).key = protocols(i).key;
    comparison(i).local_method = protocols(i).method;
    comparison(i).article_setup = articleRow.setup;
    comparison(i).delta_mean_x_m = metrics.mean_x_m - articleRow.mean_x_m;
    comparison(i).delta_mean_y_m = metrics.mean_y_m - articleRow.mean_y_m;
    comparison(i).delta_mean_Q_gps = metrics.mean_Q_gps - articleRow.mean_Q_gps;
    comparison(i).delta_mean_H_m = metrics.mean_H_m - articleRow.mean_Hr_m;
end
end

function write_article_exact_report(result)
fid = fopen(result.report_path, 'w');
if fid == -1
    error('Cannot open report for writing: %s', result.report_path);
end
cleanupObj = onCleanup(@() fclose(fid)); %#ok<NASGU>

fprintf(fid, '# Article Exact MGA/NMGA Reproduction Report\n\n');
fprintf(fid, 'Generated by `run_article_exact_reproduction(''%s'')`.\n\n', result.profile);
fprintf(fid, '## Scope\n');
fprintf(fid, '- Source: `%s`, DOI `%s`.\n', result.spec.source.title, result.spec.source.doi);
fprintf(fid, '- Data provenance: `%s`.\n', result.data_provenance);
fprintf(fid, '- Raw exact status: `%s`.\n', result.raw_exact_status);
fprintf(fid, '- Claim level: public-text exact formulas/operators/parameters; not raw-data Table 1 duplication.\n\n');

fprintf(fid, '## Encoded Article Protocol\n');
fprintf(fid, '| Item | Value |\n');
fprintf(fid, '|---|---:|\n');
fprintf(fid, '| Population | %d |\n', result.population_size);
fprintf(fid, '| Repeats | %d |\n', result.repeat_count);
fprintf(fid, '| MGA generations | %d |\n', result.protocols(1).generations);
fprintf(fid, '| NMGA long generations | %d |\n', result.protocols(2).generations);
fprintf(fid, '| NMGA short generations | %d |\n', result.protocols(3).generations);
fprintf(fid, '| P1 | %.6g |\n', result.spec.algorithm.nmga_initial_crossover_rate);
fprintf(fid, '| P2 | %.6g |\n', result.spec.algorithm.nmga_initial_mutation_rate);
fprintf(fid, '| b | %.6g |\n', result.spec.algorithm.schedule_exponent);
fprintf(fid, '| beta | %.6g |\n', result.spec.algorithm.beta);
fprintf(fid, '| gamma | %.6g |\n', result.spec.algorithm.gamma);
fprintf(fid, '| SetMax | %d |\n\n', result.spec.algorithm.SetMax);

fprintf(fid, '## Local Aggregate Results\n');
fprintf(fid, '| Method | Gens | Repeats | Mean x | Std x | Rel x %% | Mean y | Std y | Rel y %% | Mean Q | Std Q | Rel Q %% | Mean H | Std H | Rel H %% | Mean objective |\n');
fprintf(fid, '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n');
for i = 1:numel(result.protocols)
    write_metric_row(fid, result.protocols(i));
end

fprintf(fid, '\n## Table 1 Comparison\n');
fprintf(fid, 'Article Table 1 values are encoded as reference values only. Local deltas below are expected to differ while input data remain `synthetic_reproduction`.\n\n');
fprintf(fid, '| Method | Article setup | Delta mean x | Delta mean y | Delta mean Q | Delta mean H |\n');
fprintf(fid, '|---|---|---:|---:|---:|---:|\n');
for i = 1:numel(result.article_table1_comparison)
    row = result.article_table1_comparison(i);
    fprintf(fid, '| %s | %s | %.6g | %.6g | %.6g | %.6g |\n', ...
        row.local_method, row.article_setup, row.delta_mean_x_m, row.delta_mean_y_m, ...
        row.delta_mean_Q_gps, row.delta_mean_H_m);
end

fprintf(fid, '\n## Convergence Artifacts\n');
fprintf(fid, '- `result.protocols(*).convergence.best_objective` stores Figure 3-style convergence histories.\n');
fprintf(fid, '- `result.protocols(*).absolute_errors` stores Figure 4-style `[x,y,Q,H]` absolute-error arrays.\n');
fprintf(fid, '- MATLAB result file: `sandbox/results/article_exact_result.mat`.\n\n');

fprintf(fid, '## Mismatch Explanation\n');
fprintf(fid, 'The code uses article formulas, public constants, article-style SSE objective, and the Table 1 run counts. Exact Table 1 reproduction remains blocked because the article does not provide original monitoring concentrations or exact sensor coordinates in this workspace.\n\n');

fprintf(fid, '## Verification Commands\n');
fprintf(fid, '```matlab\n');
fprintf(fid, 'run_unit_tests\n');
fprintf(fid, 'run_article_exact_reproduction(''article_exact'')\n');
fprintf(fid, '```\n');
end

function write_metric_row(fid, protocol)
metrics = protocol.metrics;
fprintf(fid, '| %s | %d | %d | %.6g | %.6g | %.6g | %.6g | %.6g | %.6g | %.6g | %.6g | %.6g | %.6g | %.6g | %.6g | %.6g |\n', ...
    protocol.key, protocol.generations, metrics.count, ...
    metrics.mean_x_m, metrics.std_x_m, metrics.relative_error_x_percent, ...
    metrics.mean_y_m, metrics.std_y_m, metrics.relative_error_y_percent, ...
    metrics.mean_Q_gps, metrics.std_Q_gps, metrics.relative_error_Q_percent, ...
    metrics.mean_H_m, metrics.std_H_m, metrics.relative_error_H_percent, ...
    metrics.mean_best_objective);
end

function write_operator_audit_report(result)
fid = fopen(result.operator_audit_path, 'w');
if fid == -1
    error('Cannot open operator audit report for writing: %s', result.operator_audit_path);
end
cleanupObj = onCleanup(@() fclose(fid)); %#ok<NASGU>

fprintf(fid, '# Article Operator Audit Report\n\n');
fprintf(fid, 'Generated with profile `%s`. This checklist maps article-level requirements to local functions and tests.\n\n', result.profile);
fprintf(fid, '| Article operator / claim | Local function | Verification status |\n');
fprintf(fid, '|---|---|---|\n');
fprintf(fid, '| Chromosome `[x,y,Q,H]` | `article_exact_spec`, optimizer population rows | Unit test checks spec chromosome and bounds |\n');
fprintf(fid, '| MGA fixed `Pc/Pm` | `nmga_options`, `run_evolutionary_optimizer` | Unit test checks `Pc=0.6`, `Pm=0.01` |\n');
fprintf(fid, '| NMGA Formula 7 `Pc=P1*(1-gen/maxgen)^b` | `nmga_adaptive_rates` | Unit test checks gens 1, SetMax, 500, 1000 |\n');
fprintf(fid, '| NMGA Formula 8 `Pm=P2*(1+gen/maxgen)^b` | `nmga_adaptive_rates` | Unit test checks gens 1, SetMax, 500, 1000 |\n');
fprintf(fid, '| AGP/EGP split | `article_gene_pool_split` | Unit test uses `article_operator_probe` split counts |\n');
fprintf(fid, '| AGP/EGP inheritance branch | `article_egp_crossover`, `breed_nmga` | Unit test checks deterministic child value |\n');
fprintf(fid, '| Nonuniform mutation amplitude decreases | `article_nonuniform_delta`, `mutate_nonuniform` | Unit test compares early vs late delta |\n');
fprintf(fid, '| Article SSE objective / reciprocal fitness detail | `source_objective` | Unit test checks `article_sse` against raw SSE |\n');
fprintf(fid, '| Bounds and population-size preservation | `run_evolutionary_optimizer` | Unit test checks bounds and history lengths |\n');
fprintf(fid, '| Table 1 protocol separated from sandbox stress cases | `run_article_exact_reproduction_impl` | This report and `article_exact_report.md` mark data provenance |\n\n');
fprintf(fid, 'Remaining blocker: raw exact replication requires article_raw or digitized monitoring data, not currently available locally.\n');
end

function row = empty_run_result()
row = struct( ...
    'method', '', ...
    'generations', NaN, ...
    'seed', NaN, ...
    'best_objective', NaN, ...
    'initial_best_objective', NaN, ...
    'best_x', [NaN, NaN, NaN, NaN], ...
    'position_error_m', NaN, ...
    'x_error_m', NaN, ...
    'y_error_m', NaN, ...
    'Q_error_gps', NaN, ...
    'Q_relative_error_percent', NaN, ...
    'H_error_m', NaN, ...
    'H_relative_error_percent', NaN, ...
    'generation_to_best', NaN, ...
    'runtime_seconds', NaN, ...
    'best_objective_history', [], ...
    'mean_objective_history', [], ...
    'crossover_rate_history', [], ...
    'mutation_rate_history', []);
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
