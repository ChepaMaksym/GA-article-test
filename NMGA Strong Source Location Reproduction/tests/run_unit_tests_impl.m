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
[pcStart, pmStart] = nmga_adaptive_rates(1, 100, options);
[pcEnd, pmEnd] = nmga_adaptive_rates(100, 100, options);
assert(pcEnd < pcStart, 'NMGA adaptive crossover should decrease with generation.');
assert(pmEnd > pmStart, 'NMGA adaptive mutation should increase with generation.');
passCount = passCount + 1;

caseData = synthetic_source_cases('unit');
observation = build_synthetic_observation(caseData);
runA = run_nmga_optimizer(observation, options, options.NMGA500Generations);
assert(all(runA.best_x >= observation.bounds.lb - 1.0e-12), 'Optimizer output below lower bounds.');
assert(all(runA.best_x <= observation.bounds.ub + 1.0e-12), 'Optimizer output above upper bounds.');
passCount = passCount + 1;

runB = run_nmga_optimizer(observation, options, options.NMGA500Generations);
assert(max(abs(runA.best_x - runB.best_x)) < 1.0e-9, 'Same seed should reproduce optimizer result.');
assert(abs(runA.best_objective - runB.best_objective) < 1.0e-12, 'Same seed should reproduce optimizer objective.');
passCount = passCount + 1;

testReport = struct();
testReport.passed = true;
testReport.pass_count = passCount;
testReport.note = 'Deterministic NMGA unit tests passed.';

fprintf('Unit tests passed: %d\n', passCount);
end
