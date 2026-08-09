function run_matlab_tests()
% Independent MATLAB/GNU Octave checks for the bounded EU26-16 claim.

testDir = fileparts(mfilename('fullpath'));
candidateRoot = fileparts(fileparts(testDir));
implementationDir = fullfile(candidateRoot, 'environments', 'matlab');
addpath(implementationDir);
cleanup = onCleanup(@() rmpath(implementationDir)); %#ok<NASGU>

checkout = getenv('EU2616_UPSTREAM');
if isempty(checkout) || ~exist(checkout, 'dir')
    error('EU2616:Evidence', 'EU2616_UPSTREAM must name the exact upstream checkout');
end

contract = load_json(fullfile(candidateRoot, 'config', 'verification_contract.json'));
fixture = load_json(fullfile(candidateRoot, 'fixtures', 'transition_cases.json'));
assert_claim_boundary(contract);
test_initial_state();
caseCount = test_frozen_cases(fixture);
test_repeated_steps();
test_guard_not_clamp();
test_rounding_and_stop_order();
test_invalid_inputs();
yeast = test_yeast_structure(checkout);
write_optional_report(contract, yeast, caseCount);
fprintf(['EU26-16 MATLAB/Octave source-transition tests: PASS; ', ...
    'Table 7 replay: BLOCKED_AS_PREREGISTERED\n']);
end

function assert_claim_boundary(contract)
assert(strcmp(contract.candidate_id, 'EU26-16'));
assert(strcmp(contract.status, 'FORMULA_AND_SOURCE_TRANSITION_VALIDATION_ONLY'));
assert(strcmp(contract.readiness, 'CONDITIONAL_NONELIGIBLE'));
assert(strcmp(contract.paper_mapping, ...
    'TABLE_7_NOT_REPLAYABLE_FROM_SHIPPED_ARTIFACTS'));
assert(~contract.transition.probability_clamp);
assert(~contract.transition.global_bounds_claim);
assert(~contract.paper_protocol.table_7_target_enabled);
forbidden = to_cellstr(contract.forbidden_claims);
assert(any(strcmp(forbidden, 'PASS_FULL')));
assert(any(strcmp(forbidden, 'PASS_TABLE_7_REPLAY')));
assert(any(strcmp(forbidden, 'PASS_EMPIRICAL_REPRODUCTION')));
end

function test_initial_state()
state = eu2616_initial_state();
assert(state.crossover_probability == 0.5);
assert(state.mutation_probability == 0.5);
assert(state.best_average_fitness == single(0));
assert(state.best_fitness == single(-1));
assert(state.last_best_generation == 0);
end

function caseCount = test_frozen_cases(fixture)
cases = fixture.cases;
caseCount = numel(cases);
assert(caseCount == 8);
for index = 1:caseCount
    item = struct_item(cases, index);
    state = struct();
    state.crossover_probability = item.state.crossover_probability;
    state.mutation_probability = item.state.mutation_probability;
    state.best_average_fitness = single(item.state.best_average_fitness);
    state.best_fitness = single(item.state.best_fitness);
    state.last_best_generation = item.state.last_best_generation;
    [next, event] = eu2616_transition(state, item.generation, ...
        item.current_best_fitness, item.current_average_fitness, ...
        item.max_generations);
    expected = item.expected;
    assert_close(next.crossover_probability, ...
        expected.crossover_probability, fixture.tolerance);
    assert_close(next.mutation_probability, ...
        expected.mutation_probability, fixture.tolerance);
    assert(next.best_average_fitness == single(expected.best_average_fitness));
    assert(next.best_fitness == single(expected.best_fitness));
    assert(next.last_best_generation == expected.last_best_generation);
    assert(strcmp(event.average_branch, expected.average_branch));
    assert(event.probabilities_changed == expected.probabilities_changed);
    assert(event.should_stop == expected.should_stop);
    assert_close(next.crossover_probability + next.mutation_probability, 1, ...
        fixture.tolerance);
end
end

function test_repeated_steps()
state = eu2616_initial_state();
for generation = 1:30
    [state, ~] = eu2616_transition(state, generation, ...
        0.5 + generation / 10000, generation / 100, 200);
end
assert_close(state.crossover_probability, 0.96, 1e-12);
assert_close(state.mutation_probability, 0.04, 1e-12);
assert(state.best_average_fitness == single(0.30));

state = eu2616_initial_state();
state.best_average_fitness = single(1);
for generation = 1:30
    [state, ~] = eu2616_transition(state, generation, -1, 0.5, 200);
end
assert_close(state.crossover_probability, 0.04, 1e-12);
assert_close(state.mutation_probability, 0.96, 1e-12);
end

function test_guard_not_clamp()
state = make_state(0.95, 0.05, 0.2, 0.5, 1);
[next, event] = eu2616_transition(state, 2, 0.5, 0.3, 200);
assert_close(next.crossover_probability, 0.97, 1e-12);
assert_close(next.mutation_probability, 0.03, 1e-12);
assert(event.probabilities_changed);

state = make_state(0.05, 0.95, 0.3, 0.5, 1);
[next, event] = eu2616_transition(state, 2, 0.5, 0.2, 200);
assert_close(next.crossover_probability, 0.03, 1e-12);
assert_close(next.mutation_probability, 0.97, 1e-12);
assert(event.probabilities_changed);

state = make_state(0.96, 0.04, 0.2, 0.5, 1);
[next, event] = eu2616_transition(state, 2, 0.5, 0.3, 200);
assert_close(next.crossover_probability, 0.96, 1e-12);
assert_close(next.mutation_probability, 0.04, 1e-12);
assert(next.best_average_fitness == single(0.3));
assert(~event.probabilities_changed);
end

function test_rounding_and_stop_order()
assert(eu2616_round_best_fitness(0.12344) == single(0.1234));
assert(eu2616_round_best_fitness(0.12345) == single(0.1235));
assert(eu2616_round_best_fitness(-0.12345) == single(-0.1234));

state = make_state(0.5, 0.5, 0.3, 0.5, 1);
[next, event] = eu2616_transition(state, 11, 0.50006, 0.31, 200);
assert(next.best_fitness == single(0.5001));
assert(next.last_best_generation == 11);
assert(~event.should_stop);

state = make_state(0.5, 0.5, 0, -1, 0);
[next, event] = eu2616_transition(state, 1, 0.1, 0.1, 1);
assert_close(next.crossover_probability, 0.52, 1e-12);
assert(event.should_stop);
assert(strcmp(event.stop_reason, 'max_generations'));

state = make_state(0.5, 0.5, 0.3, 0.5, 0);
[~, event] = eu2616_transition(state, 10, 0.5, 0.2, 10);
assert(strcmp(event.stop_reason, 'max_generations'));
end

function test_invalid_inputs()
state = eu2616_initial_state();
bad = state;
bad.mutation_probability = 0.4;
assert_throws(@() eu2616_transition(bad, 1, 0.1, 0.1, 200), 'EU2616:Input');
bad = state;
bad.crossover_probability = 1.01;
bad.mutation_probability = -0.01;
assert_throws(@() eu2616_transition(bad, 1, 0.1, 0.1, 200), 'EU2616:Input');
bad = state;
bad.best_fitness = 'x';
assert_throws(@() eu2616_transition(bad, 1, 0.1, 0.1, 200), 'EU2616:Input');
assert_throws(@() eu2616_transition(state, -1, 0.1, 0.1, 200), 'EU2616:Input');
assert_throws(@() eu2616_transition(state, 1, NaN, 0.1, 200), 'EU2616:Input');
assert_throws(@() eu2616_transition(state, 1, 0.1, Inf, 200), 'EU2616:Input');
assert_throws(@() eu2616_transition(state, 1, 0.1, 0.1, 0), 'EU2616:Input');
end

function yeast = test_yeast_structure(checkout)
yeast = eu2616_parse_yeast(checkout);
assert(isequal(yeast.seeds, [10, 20, 100]));
assert(yeast.input_count == 103);
assert(yeast.label_count == 14);
assert(yeast.train_rows == 1933);
assert(yeast.test_rows == 484);
assert(yeast.total_rows == 2417);
assert(~yeast.paper_replay_ready);
missing = to_cellstr(yeast.missing_paths);
assert(numel(missing) == 2);
assert(any(strcmp(missing, 'data/Yeast/Yeast-train2.arff')));
assert(any(strcmp(missing, 'data/Yeast/Yeast-test2.arff')));
end

function write_optional_report(contract, yeast, caseCount)
output = getenv('EU2616_OCTAVE_REPORT');
if isempty(output)
    return;
end
if exist(output, 'file')
    error('EU2616:Output', 'refusing to overwrite an existing report');
end
report = struct();
report.schema_version = '1.0.0';
report.candidate_id = 'EU26-16';
report.status = 'PASS_MATLAB_OCTAVE_INDEPENDENT';
report.readiness = contract.readiness;
report.paper_mapping = contract.paper_mapping;
report.transition_case_count = caseCount;
report.input_count = yeast.input_count;
report.label_count = yeast.label_count;
report.table_7_status = 'BLOCKED_AS_PREREGISTERED';
report.empirical_claim_made = false;
report.forbidden_claims = contract.forbidden_claims;
encoded = jsonencode(report);
[handle, message] = fopen(output, 'w');
if handle < 0
    error('EU2616:Output', 'cannot create report: %s', message);
end
cleanup = onCleanup(@() fclose(handle)); %#ok<NASGU>
fprintf(handle, '%s\n', encoded);
end

function state = make_state(pc, pm, bestAverage, bestFitness, lastBest)
state = struct();
state.crossover_probability = pc;
state.mutation_probability = pm;
state.best_average_fitness = single(bestAverage);
state.best_fitness = single(bestFitness);
state.last_best_generation = lastBest;
end

function value = load_json(path)
if exist('jsondecode', 'builtin') == 0 && exist('jsondecode', 'file') == 0
    error('EU2616:Environment', 'jsondecode is required');
end
value = jsondecode(fileread(path));
end

function value = struct_item(values, index)
if iscell(values)
    value = values{index};
else
    value = values(index);
end
end

function values = to_cellstr(values)
if ischar(values)
    values = {values};
elseif isstring(values)
    values = cellstr(values);
elseif ~iscell(values)
    values = cellstr(values);
end
end

function assert_close(actual, expected, tolerance)
assert(isfinite(actual));
assert(abs(double(actual) - double(expected)) <= tolerance);
end

function assert_throws(callback, identifier)
didThrow = false;
try
    callback();
catch exception
    didThrow = true;
    assert(strcmp(exception.identifier, identifier));
end
assert(didThrow);
end
