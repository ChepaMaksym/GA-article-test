function run_octave_tests
% Independent MATLAB/Octave control suite and canonical JSON report.
test_root = fileparts(mfilename('fullpath'));
candidate_root = fileparts(fileparts(test_root));
addpath(fullfile(candidate_root, 'environments', 'matlab'));
contract_path = fullfile(candidate_root, 'config', 'verification_contract.json');
contract = jsondecode(fileread(contract_path));
assertions = 0;

assert(strcmp(contract.candidate_id, 'EU26-12')); assertions = assertions + 1;
assert(strcmp(contract.status, 'TARGETED_ARTIFACT_REPLAY_ONLY')); assertions = assertions + 1;
assert(strcmp(contract.paper_mapping, 'PAPER_EXPERIMENT_ARTIFACT_MAPPING')); assertions = assertions + 1;
assert(any(strcmp(contract.forbidden_claims, 'PASS_FULL'))); assertions = assertions + 1;
assert(any(strcmp(contract.forbidden_claims, 'FULL_ARCHIVE_MD5_RECOMPUTED'))); assertions = assertions + 1;
assert(any(strcmp(contract.forbidden_claims, 'EXACT_ARTIFACT_GIT_TREE_MATCH'))); assertions = assertions + 1;

memory = eu2612_memory_update([10, 8, 5], [9, 6, 4.5], [0.2, 0.4, 0.8], [0.1, 0.5, 0.9]);
assert(isequal(memory.successful_indices, [0, 1, 2])); assertions = assertions + 1;
assert(max(abs(memory.weights - [2/7, 4/7, 1/7])) < 1e-14); assertions = assertions + 1;
assert(abs(memory.F - 0.4) < 1e-14); assertions = assertions + 1;
assert(abs(memory.CR - 31/70) < 1e-14); assertions = assertions + 1;

cr_values = eu2612_transform_cr(0.5, [-10, 0, 10]);
assert(isequal(cr_values, [0, 0.5, 1])); assertions = assertions + 1;
f_values = eu2612_transform_f(0.5, {[-6, -4], [8], [0]});
assert(max(abs(f_values - [0.1, 1, 0.5])) < 1e-14); assertions = assertions + 1;

replacement = eu2612_replacement([1, 2, 3], [1, 1.5, 4]);
assert(isequal(replacement.sources, {'offspring', 'offspring', 'parent'})); assertions = assertions + 1;
assert(isequal(replacement.improved, [false, true, false])); assertions = assertions + 1;
assert(eu2612_round_ties_even(2.5) == 2); assertions = assertions + 1;
assert(eu2612_round_ties_even(3.5) == 4); assertions = assertions + 1;
assert(eu2612_lpsr(360, 3, 50000, 0) == 360); assertions = assertions + 1;
assert(eu2612_lpsr(360, 3, 50000, 49642) == 6); assertions = assertions + 1;

schedule = eu2612_schedule(360, 3, 50000);
assert(schedule.generations == 582); assertions = assertions + 1;
assert(schedule.used_budget == 49642); assertions = assertions + 1;
assert(schedule.logged_evaluations == 50002); assertions = assertions + 1;
assert(schedule.terminal_population == 6); assertions = assertions + 1;

assert(strcmp(eu2612_fraction_decimal(2, 7, 50), '0.28571428571428571428571428571428571428571428571429')); assertions = assertions + 1;
assert(strcmp(eu2612_fraction_decimal(4, 7, 50), '0.57142857142857142857142857142857142857142857142857')); assertions = assertions + 1;
assert(strcmp(eu2612_fraction_decimal(1, 7, 50), '0.14285714285714285714285714285714285714285714285714')); assertions = assertions + 1;
assert(strcmp(eu2612_fraction_decimal(2, 5, 50), '0.4')); assertions = assertions + 1;
assert(strcmp(eu2612_fraction_decimal(31, 70, 50), '0.44285714285714285714285714285714285714285714285714')); assertions = assertions + 1;

control_fixtures = struct();
control_fixtures.memory_successful_indices = [0, 1, 2];
control_fixtures.memory_weights = { ...
    eu2612_fraction_decimal(2, 7, 50), ...
    eu2612_fraction_decimal(4, 7, 50), ...
    eu2612_fraction_decimal(1, 7, 50)};
control_fixtures.memory_F = eu2612_fraction_decimal(2, 5, 50);
control_fixtures.memory_CR = eu2612_fraction_decimal(31, 70, 50);
control_fixtures.CR_values = {'0', '0.5', '1'};
control_fixtures.F_values = {'0.1', '1', '0.5'};
control_fixtures.replacement_sources = replacement.sources;
control_fixtures.replacement_improved = replacement.improved;
control_fixtures.schedule = schedule;
control_fixtures.round_half_even = struct('two_point_five', 2, 'three_point_five', 4);

assert(strcmp(control_fixtures.memory_F, contract.control_fixtures.memory_update.expected_F)); assertions = assertions + 1;
assert(strcmp(control_fixtures.memory_CR, contract.control_fixtures.memory_update.expected_CR)); assertions = assertions + 1;
assert(isequal(control_fixtures.schedule.logged_evaluations, contract.endpoint.logged_evaluations)); assertions = assertions + 1;
assert(isequal(control_fixtures.replacement_sources(:), contract.control_fixtures.replacement.expected_sources(:))); assertions = assertions + 1;
assert(assertions >= 30); assertions = assertions + 1;

report = struct();
report.schema_version = '1.0.0';
report.candidate_id = 'EU26-12';
report.status = 'PASS_MATLAB_OCTAVE_INDEPENDENT_CONTROLS';
report.paper_mapping = contract.paper_mapping;
report.control_fixtures = control_fixtures;
report.assertions = assertions;
report.forbidden_claims = contract.forbidden_claims;

output = getenv('EU2612_OCTAVE_REPORT');
if isempty(output)
    error('EU2612:OutputMissing', 'EU2612_OCTAVE_REPORT must name a new report path.');
end
if exist(output, 'file') || exist(output, 'dir')
    error('EU2612:OutputExists', 'Octave report path already exists.');
end
[descriptor, message] = fopen(output, 'w');
if descriptor < 0
    error('EU2612:OutputOpen', 'Cannot create report: %s', message);
end
cleanup = onCleanup(@() fclose(descriptor));
fprintf(descriptor, '%s\n', jsonencode(report));
fprintf('PASS_MATLAB_OCTAVE_INDEPENDENT_CONTROLS: %d assertions\n', assertions);
end
