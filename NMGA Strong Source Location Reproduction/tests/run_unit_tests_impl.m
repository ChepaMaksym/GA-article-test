function testReport = run_unit_tests_impl()
projectRoot = fileparts(fileparts(mfilename('fullpath')));
addpath(genpath(fullfile(projectRoot, 'src')));

passCount = 0;

structureReport = verify_project_structure(projectRoot);
assert(structureReport.passed, 'Project structure check failed.');
passCount = passCount + 1;

source = [-25, 16, 15178.32, 2];
sensors = synthetic_sensor_grid('figure_eight');
concentration = gaussian_plume_concentration(source, sensors, 2.0);
assert(all(isfinite(concentration)), 'Gaussian plume concentration must be finite.');
assert(any(concentration > 0), 'Gaussian plume must return positive downwind concentrations.');
passCount = passCount + 1;

centerSensor = struct('x_m', 80, 'y_m', 16, 'z_m', 1.5);
sideSensor = struct('x_m', 80, 'y_m', 80, 'z_m', 1.5);
centerC = gaussian_plume_concentration(source, centerSensor, 2.0);
sideC = gaussian_plume_concentration(source, sideSensor, 2.0);
assert(centerC > sideC, 'Concentration should decrease away from the plume centerline.');
passCount = passCount + 1;

upwindSensor = struct('x_m', -100, 'y_m', 16, 'z_m', 1.5);
upwindC = gaussian_plume_concentration(source, upwindSensor, 2.0);
assert(upwindC == 0, 'Upwind concentration should be handled as zero.');
passCount = passCount + 1;

options = nmga_options('NMGA', 'unit', 20260428);
article = article_reported();
spec = article_exact_spec();
assert(isequal(spec.algorithm.chromosome, {'x_m', 'y_m', 'Q_gps', 'H_m'}), ...
    'Article exact chromosome must be [x,y,Q,H].');
assert(abs(article.algorithm.mga_crossover_rate - 0.6) < 1.0e-12, ...
    'MGA fixed crossover rate must match article parameter.');
assert(abs(article.algorithm.mga_mutation_rate - 0.01) < 1.0e-12, ...
    'MGA fixed mutation rate must match article parameter.');
assert(options.NMGACrossoverInitial == article.algorithm.nmga_initial_crossover_rate, ...
    'NMGA initial crossover rate must match article Formula 7 parameter P1.');
assert(options.NMGAMutationInitial == article.algorithm.nmga_initial_mutation_rate, ...
    'NMGA initial mutation rate must match article Formula 8 parameter P2.');
assert(options.NMGAScheduleExponent == article.algorithm.nmga_schedule_exponent, ...
    'NMGA schedule exponent must match article parameter b.');
assert(abs(article.table1(1).std_x_m - 1.04) < 1.0e-12, 'Article Table 1 MGA x std mismatch.');
assert(abs(article.table1(3).relative_error_Q_percent - 0.038) < 1.0e-12, 'Article Table 1 NMGA 500 Q relative error mismatch.');
mgaOptions = nmga_options('MGA', 'unit', 20260428);
assert(abs(mgaOptions.MGACrossoverRate - 0.6) < 1.0e-12, 'MGA options must use fixed Pc=0.6.');
assert(abs(mgaOptions.MGAMutationRate - 0.01) < 1.0e-12, 'MGA options must use fixed Pm=0.01.');
articleOptions = nmga_options('NMGA', 'article_exact', 20260428);
assert(articleOptions.RepeatCount == 100, 'Article exact profile must use 100 repeats.');
assert(articleOptions.MGAGenerations == 2000, 'Article exact profile must use MGA 2000 generations.');
assert(articleOptions.NMGA1000Generations == 1000, 'Article exact profile must use NMGA 1000 generations.');
assert(articleOptions.NMGA500Generations == 500, 'Article exact profile must use NMGA 500 generations.');
assert(strcmp(articleOptions.ObjectiveMode, 'article_sse'), 'Article exact profile must use article_sse objective.');
assert(strcmp(articleOptions.OperatorMode, 'article_exact'), 'Article exact profile must use article operators.');
[pcStart, pmStart] = nmga_adaptive_rates(1, 100, options);
[pcEnd, pmEnd] = nmga_adaptive_rates(100, 100, options);
assert(pcEnd < pcStart, 'NMGA adaptive crossover should decrease with generation.');
assert(pmEnd > pmStart, 'NMGA adaptive mutation should increase with generation.');
pcHistory = zeros(100, 1);
pmHistory = zeros(100, 1);
pcExpected = zeros(100, 1);
pmExpected = zeros(100, 1);
for g = 1:100
    [pcHistory(g), pmHistory(g)] = nmga_adaptive_rates(g, 100, options);
    progress = g / 100;
    pcExpected(g) = options.NMGACrossoverInitial * (1 - progress) ^ options.NMGAScheduleExponent;
    pmExpected(g) = options.NMGAMutationInitial * (1 + progress) ^ options.NMGAScheduleExponent;
end
assert(all(diff(pcHistory) <= 1.0e-12), 'NMGA crossover schedule must be monotonically non-increasing.');
assert(all(diff(pmHistory) >= -1.0e-12), 'NMGA mutation schedule must be monotonically non-decreasing.');
assert(max(abs(pcHistory - pcExpected)) < 1.0e-12, 'NMGA crossover schedule must follow article Formula 7.');
assert(max(abs(pmHistory - pmExpected)) < 1.0e-12, 'NMGA mutation schedule must follow article Formula 8.');
assert(min(pcHistory) >= options.NMGACrossoverMin - 1.0e-12, 'NMGA crossover below configured lower bound.');
assert(max(pcHistory) <= options.NMGACrossoverMax + 1.0e-12, 'NMGA crossover above configured upper bound.');
assert(min(pmHistory) >= options.NMGAMutationMin - 1.0e-12, 'NMGA mutation below configured lower bound.');
assert(max(pmHistory) <= options.NMGAMutationMax + 1.0e-12, 'NMGA mutation above configured upper bound.');

checkGenerations = [1, spec.algorithm.SetMax, 500, 1000];
for idx = 1:numel(checkGenerations)
    g = checkGenerations(idx);
    [pcFormula, pmFormula] = nmga_adaptive_rates(g, 1000, articleOptions);
    progress = g / 1000;
    pcExpected = spec.algorithm.nmga_initial_crossover_rate * (1 - progress) ^ spec.algorithm.schedule_exponent;
    pmExpected = spec.algorithm.nmga_initial_mutation_rate * (1 + progress) ^ spec.algorithm.schedule_exponent;
    assert(abs(pcFormula - pcExpected) < 1.0e-12, 'Article Formula 7 Pc value mismatch.');
    assert(abs(pmFormula - pmExpected) < 1.0e-12, 'Article Formula 8 Pm value mismatch.');
end
passCount = passCount + 1;

probe = article_operator_probe();
assert(probe.agp_count == 3, 'AGP split count mismatch.');
assert(probe.egp_count == 2, 'EGP split count mismatch.');
assert(all(probe.agp(1, :) == [2, 7, 12, 17]), 'AGP should start from the best fitness parent.');
assert(all(probe.egp(1, :) == [3, 8, 13, 18]), 'EGP should contain lower-fitness parents after AGP.');
assert(max(abs(probe.egp_child - probe.expected_egp_child)) < 1.0e-12, 'EGP inheritance child mismatch.');
assert(probe.early_delta > probe.late_delta, 'Nonuniform mutation delta must shrink over generations.');
passCount = passCount + 1;

caseData = synthetic_source_cases('unit');
observation = build_synthetic_observation(caseData);
articleObservation = observation;
articleObservation.objective_mode = 'article_sse';
[normalizedObjective, normalizedDetails] = source_objective(observation.true_source, observation);
[articleObjective, articleDetails] = source_objective(articleObservation.true_source, articleObservation);
assert(strcmp(normalizedDetails.objective_mode, 'normalized_mse'), 'Default objective must remain normalized_mse.');
assert(strcmp(articleDetails.objective_mode, 'article_sse'), 'Article exact objective mode mismatch.');
assert(abs(articleObjective - articleDetails.raw_sse) < 1.0e-12, 'Article objective must equal raw SSE.');
assert(articleDetails.article_style_fitness >= 1 / eps, 'Article fitness detail should use reciprocal raw SSE protection.');
assert(normalizedObjective <= 1.0e-20, 'Synthetic true source should have near-zero normalized objective.');
passCount = passCount + 1;

articleUnitOptions = options;
articleUnitOptions.ObjectiveMode = 'article_sse';
articleUnitOptions.OperatorMode = 'article_exact';
articleUnitOptions.ArticleExact = true;
runA = run_nmga_optimizer(observation, articleUnitOptions, articleUnitOptions.NMGA500Generations);
assert(all(runA.best_x >= observation.bounds.lb - 1.0e-12), 'Optimizer output below lower bounds.');
assert(all(runA.best_x <= observation.bounds.ub + 1.0e-12), 'Optimizer output above upper bounds.');
assert(numel(runA.history.bestObjective) == articleUnitOptions.NMGA500Generations, 'Best objective history length mismatch.');
assert(numel(runA.history.crossoverRate) == articleUnitOptions.NMGA500Generations, 'Crossover history length mismatch.');
assert(numel(runA.history.mutationRate) == articleUnitOptions.NMGA500Generations, 'Mutation history length mismatch.');
assert(numel(runA.history.populationDiversity) == articleUnitOptions.NMGA500Generations, 'Diversity history length mismatch.');
assert(numel(runA.history.stagnationCount) == articleUnitOptions.NMGA500Generations, 'Stagnation history length mismatch.');
assert(all(isfinite(runA.history.populationDiversity)), 'Diversity history must be finite.');
assert(all(isfinite(runA.history.stagnationCount)), 'Stagnation history must be finite.');
assert(isfinite(runA.generation_to_best), 'Generation-to-best must be finite.');
assert(isfinite(runA.runtime_seconds), 'Runtime must be finite.');
passCount = passCount + 1;

runB = run_nmga_optimizer(observation, articleUnitOptions, articleUnitOptions.NMGA500Generations);
assert(max(abs(runA.best_x - runB.best_x)) < 1.0e-9, 'Same seed should reproduce optimizer result.');
assert(abs(runA.best_objective - runB.best_objective) < 1.0e-12, 'Same seed should reproduce optimizer objective.');
passCount = passCount + 1;

articleSmoke = run_article_exact_reproduction_impl('unit');
assert(strcmp(articleSmoke.data_provenance, 'synthetic_reproduction'), 'Article smoke report must mark synthetic data provenance.');
assert(strcmp(articleSmoke.raw_exact_status, 'blocked_without_article_raw_sensor_coordinates_and_observed_concentrations'), ...
    'Article smoke report must keep raw exact replication blocked.');
assert(isfile(articleSmoke.report_path), 'Article exact report was not written.');
assert(isfile(articleSmoke.operator_audit_path), 'Operator audit report was not written.');
passCount = passCount + 1;

auditA = run_nmga_adaptive_audit_impl('unit', false);
auditB = run_nmga_adaptive_audit_impl('unit', false);
assert(auditA.article_fidelity.pc_monotonic_decrease, 'Audit must confirm Pc monotonic decrease.');
assert(auditA.article_fidelity.pm_monotonic_increase, 'Audit must confirm Pm monotonic increase.');
assert(auditA.acceptance.history_metrics_finite, 'Audit history metrics must be finite.');
assert(abs(auditA.acceptance.baseline_median_position_error_m - auditB.acceptance.baseline_median_position_error_m) < 1.0e-9, ...
    'Same audit profile should reproduce baseline median error.');
assert(max(abs(auditA.cases(1).estimated_source - auditB.cases(1).estimated_source)) < 1.0e-9, ...
    'Same audit profile should reproduce first estimated source.');
passCount = passCount + 1;

testReport = struct();
testReport.passed = true;
testReport.pass_count = passCount;
testReport.note = 'Deterministic NMGA unit tests passed.';

fprintf('Unit tests passed: %d\n', passCount);
end
