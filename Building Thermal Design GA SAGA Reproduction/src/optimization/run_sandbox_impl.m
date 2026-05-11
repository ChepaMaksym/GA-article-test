function sandbox = run_sandbox_impl()
projectRoot = find_project_root();
resultsDir = fullfile(projectRoot, 'sandbox', 'results');
if exist(resultsDir, 'dir') ~= 7
    mkdir(resultsDir);
end

caseList = building_cases(7);
caseDef = caseList(1);
scenarios = synthetic_sandbox_scenarios();
checks = repmat(empty_sandbox_check(), 1, numel(scenarios));

for i = 1:numel(scenarios)
    seed = 20260503 + i;
    [gaOptions, sagaOptions] = configure_options_for_scenario(seed, scenarios(i));
    problem = building_problem(caseDef, false, scenarios(i));
    gaResult = run_classical_ga(problem, gaOptions);
    sagaResult = run_saga_optimizer(problem, sagaOptions);
    criterion = satisfies_saga_criterion(sagaResult);
    checks(i) = make_sandbox_check(scenarios(i), gaResult, sagaResult, criterion, problem);
end

sandbox = struct();
sandbox.case = caseDef;
sandbox.scenarios = scenarios;
sandbox.checks = checks;
sandbox.all_saga_checks_passed = all([checks.saga_criterion_passed]) && ...
    all([checks.bounds_passed]) && all([checks.theta_bounds_passed]) && ...
    all([checks.equal_budget_passed]) && all([checks.theta_history_passed]);
sandbox.report_path = fullfile(resultsDir, 'saga_sandbox_report.md');
sandbox.mat_path = fullfile(resultsDir, 'saga_sandbox_result.mat');

save(sandbox.mat_path, 'sandbox');
write_sandbox_report(sandbox);

fprintf('SAGA sandbox report written to: %s\n', sandbox.report_path);
fprintf('SAGA sandbox MAT written to: %s\n', sandbox.mat_path);
end

function check = empty_sandbox_check()
check = struct();
check.scenario_name = '';
check.ga_lcc_eur = [];
check.saga_lcc_eur = [];
check.saga_criterion_passed = false;
check.bounds_passed = false;
check.theta_bounds_passed = false;
check.equal_budget_passed = false;
check.theta_history_passed = false;
check.selection_complete_passed = false;
check.no_external_update_passed = false;
check.message = '';
end

function check = make_sandbox_check(scenario, gaResult, sagaResult, criterion, problem)
theta = saga_theta_matrix_from_history(sagaResult.history.theta_population_history);
thetaBounds = [sagaResult.options.ThetaBounds.Pm; sagaResult.options.ThetaBounds.Pc; sagaResult.options.ThetaBounds.sigma];

check = empty_sandbox_check();
check.scenario_name = scenario.name;
check.ga_lcc_eur = gaResult.best_lcc_eur;
check.saga_lcc_eur = sagaResult.best_lcc_eur;
check.saga_criterion_passed = criterion.passed;
check.bounds_passed = all(sagaResult.best_x >= problem.lb - 1.0e-12) && all(sagaResult.best_x <= problem.ub + 1.0e-12);
check.theta_bounds_passed = all(theta(:, 1) >= thetaBounds(1, 1) - 1.0e-12) && all(theta(:, 1) <= thetaBounds(1, 2) + 1.0e-12) && ...
    all(theta(:, 2) >= thetaBounds(2, 1) - 1.0e-12) && all(theta(:, 2) <= thetaBounds(2, 2) + 1.0e-12) && ...
    all(theta(:, 3) >= thetaBounds(3, 1) - 1.0e-12) && all(theta(:, 3) <= thetaBounds(3, 2) + 1.0e-12);
check.equal_budget_passed = gaResult.function_evaluations == sagaResult.function_evaluations;
check.theta_history_passed = size(sagaResult.history.theta_population_history, 3) == sagaResult.options.MaxGenerations;
check.selection_complete_passed = sagaResult.diagnostics.selection_returns_complete_individual;
check.no_external_update_passed = ~sagaResult.diagnostics.external_theta_update && ...
    ~sagaResult.diagnostics.generation_based_theta_update && ...
    ~sagaResult.diagnostics.stagnation_based_theta_update && ...
    ~sagaResult.diagnostics.diversity_based_theta_update;
check.message = criterion.message;
end

function theta = saga_theta_matrix_from_history(thetaHistory)
[nPop, nTheta, nGen] = size(thetaHistory);
theta = zeros(nPop * nGen, nTheta);
for generation = 1:nGen
    rows = (generation - 1) * nPop + (1:nPop);
    theta(rows, :) = thetaHistory(:, :, generation);
end
end

function write_sandbox_report(sandbox)
fid = fopen(sandbox.report_path, 'w');
if fid == -1
    error('Cannot open sandbox report: %s', sandbox.report_path);
end
cleanupObj = onCleanup(@() fclose(fid)); %#ok<NASGU>

fprintf(fid, '# Formal SAGA Sandbox Report\n\n');
fprintf(fid, '- Case: %d (%s)\n', sandbox.case.id, sandbox.case.label);
fprintf(fid, '- All checks passed: %d\n\n', sandbox.all_saga_checks_passed);

fprintf(fid, '| Scenario | GA LCC EUR | SAGA LCC EUR | Criterion | Bounds | Theta bounds | Equal budget | Theta history | No external update |\n');
fprintf(fid, '|---|---:|---:|---|---|---|---|---|---|\n');
for i = 1:numel(sandbox.checks)
    row = sandbox.checks(i);
    fprintf(fid, '| %s | %.3f | %.3f | %s | %s | %s | %s | %s | %s |\n', ...
        row.scenario_name, row.ga_lcc_eur, row.saga_lcc_eur, ...
        passfail(row.saga_criterion_passed), passfail(row.bounds_passed), ...
        passfail(row.theta_bounds_passed), passfail(row.equal_budget_passed), ...
        passfail(row.theta_history_passed), passfail(row.no_external_update_passed));
end

fprintf(fid, '\nThe sandbox passes only when formal SAGA mechanics are visible in logs and GA/SAGA share the same objective, bounds, population size, generation count, and seed policy.\n');
end

function text = passfail(value)
if value
    text = 'PASS';
else
    text = 'FAIL';
end
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
