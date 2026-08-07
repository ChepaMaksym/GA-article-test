function run_matlab_tests()
%RUN_MATLAB_TESTS Outcome-blind EU26-05 MATLAB/Octave test suite.

tests_directory = fileparts(mfilename('fullpath'));
candidate = fileparts(fileparts(tests_directory));
addpath(fullfile(candidate, 'environments', 'matlab'));

test_probability_update();
test_probability_grid();
test_probability_rejections();
test_decode_anchor();
test_transition_fixture();
test_exhaustive_small_crossovers();
test_objective_anchor();
test_shared_fixture();

fprintf('EU26-05 MATLAB/OCTAVE FORMULA TESTS PASS\n');
end

function test_probability_update()
assert(isequal(eu2605_probability_update([0, 0, 0, 0], [1, 2, 3, 4]), ...
    [0.25, 0.25, 0.25, 0.25]));
assert(max(abs(eu2605_probability_update([3, 0, 0, 0], [3, 4, 5, 6]) ...
    - [0.70, 0.10, 0.10, 0.10])) < 1e-12);
assert(max(abs(eu2605_probability_update([1, 2, 1, 0], [2, 4, 4, 8]) ...
    - [0.34, 0.34, 0.22, 0.10])) < 1e-12);
end

function test_probability_grid()
checked = 0;
for first = 0:1
    for second = 0:2
        for third = 0:3
            for fourth = 0:4
                probabilities = eu2605_probability_update( ...
                    [first, second, third, fourth], [1, 2, 3, 4]);
                assert(abs(sum(probabilities) - 1) < 1e-12);
                assert(all(probabilities >= 0.10 - 1e-12));
                assert(all(probabilities <= 0.70 + 1e-12));
                checked = checked + 1;
            end
        end
    end
end
assert(checked == 120);
end

function test_probability_rejections()
for index = 1:4
    totals = ones(1, 4);
    totals(index) = 0;
    assert_throws(@() eu2605_probability_update(zeros(1, 4), totals), ...
        'EU2605:BadProbabilityInput');
end
assert_throws(@() eu2605_probability_update([2, 0, 0, 0], ones(1, 4)), ...
    'EU2605:BadProbabilityInput');
assert_throws(@() eu2605_probability_update([1, 0, 0], ones(1, 4)), ...
    'EU2605:BadProbabilityInput');
assert_throws(@() eu2605_probability_update([1.5, 0, 0, 0], ones(1, 4)), ...
    'EU2605:BadProbabilityInput');
end

function test_decode_anchor()
assert(eu2605_binary_decode_anchor( ...
    '0000', -100, 100, 'msb_first', 'closed_linear') == -100);
assert(eu2605_binary_decode_anchor( ...
    '1111', -100, 100, 'msb_first', 'closed_linear') == 100);
assert(abs(eu2605_binary_decode_anchor( ...
    '1000', -100, 100, 'msb_first', 'closed_linear') - 100 / 15) < 1e-12);
assert(abs(eu2605_binary_decode_anchor( ...
    '1000', -100, 100, 'lsb_first', 'closed_linear') + 1300 / 15) < 1e-12);
assert_throws(@() eu2605_binary_decode_anchor( ...
    '10x0', -100, 100, 'msb_first', 'closed_linear'), ...
    'EU2605:BadDecodeInput');
assert_throws(@() eu2605_binary_decode_anchor( ...
    '1000', -100, 100, 'unknown', 'closed_linear'), ...
    'EU2605:BadDecodeInput');
assert_throws(@() eu2605_binary_decode_anchor( ...
    '1000', -100, 100, 'msb_first', 'half_open'), ...
    'EU2605:BadDecodeInput');
end

function test_transition_fixture()
transition = eu2605_crossover_transition( ...
    '00001111', '11110000', 0, 4);
assert(strcmp(transition.operator, 'one_point_explicit_cut'));
assert(isequal(transition.children, {'00000000', '11111111'}));
transition = eu2605_crossover_transition('001101', '011001', 3, []);
assert(strcmp(transition.operator, ...
    'thesis_maximum_extension_complement_origin'));
assert(isequal(transition.children, {'110010', '100110'}));

assert_throws(@() eu2605_crossover_transition('00', '11', 0, []), ...
    'EU2605:BadTransitionInput');
assert_throws(@() eu2605_crossover_transition('00', '11', 3, 1), ...
    'EU2605:BadTransitionInput');
assert_throws(@() eu2605_crossover_transition('00', '11', 4, 1), ...
    'EU2605:BadTransitionInput');
end

function test_exhaustive_small_crossovers()
values = cell(1, 16);
for value = 0:15
    values{value + 1} = dec2bin(value, 4);
end
one_point_checked = 0;
extension_checked = 0;
for first_index = 1:numel(values)
    for second_index = 1:numel(values)
        first = values{first_index};
        second = values{second_index};
        parent_distance = sum(first ~= second);
        for cut = 1:3
            transition = eu2605_crossover_transition(first, second, 0, cut);
            for child_index = 1:2
                child = transition.children{child_index};
                assert(sum(first ~= child) + sum(child ~= second) ...
                    == parent_distance);
            end
            one_point_checked = one_point_checked + 1;
        end
        transition = eu2605_crossover_transition(first, second, 3, []);
        assert(strcmp(transition.children{1}, complement(first)));
        assert(strcmp(transition.children{2}, complement(second)));
        extension_checked = extension_checked + 2;
    end
end
assert(one_point_checked == 768);
assert(extension_checked == 512);
end

function test_objective_anchor()
result = eu2605_objective_interface_anchor( ...
    repmat('0', 1, 600), @(coordinates) sum(coordinates .^ 2), ...
    'msb_first', 'closed_linear', false);
assert(isequal(result.coordinates, -100 * ones(1, 30)));
assert(result.value == 300000);
assert(strcmp(result.objective_kind, 'toy_injected'));
assert_throws(@() eu2605_objective_interface_anchor( ...
    repmat('0', 1, 600), @sum, 'msb_first', 'closed_linear', true), ...
    'EU2605:BadObjectiveAnchor');
assert_throws(@() eu2605_objective_interface_anchor( ...
    repmat('0', 1, 599), @sum, 'msb_first', 'closed_linear', false), ...
    'EU2605:BadObjectiveAnchor');
end

function test_shared_fixture()
report_path = [tempname(), '.json'];
cleanup = onCleanup(@() delete_if_exists(report_path)); %#ok<NASGU>
report = run_shared_fixture_report(report_path);
assert(strcmp(report.source_byte_status, 'PASS_METADATA_ONLY'));
assert(strcmp(report.source_freeze_status, 'BLOCKED_SOURCE_BYTE_FREEZE'));
assert(strcmp(report.h0_source_status, ...
    'PASS_METADATA_ONLY / BLOCKED_SOURCE_BYTE_FREEZE'));
assert(strcmp(report.implementation, 'matlab_octave'));
assert(strcmp(report.execution_authentication, ...
    'SELF_ASSERTED_RUNTIME_CONTEXT_ONLY'));
assert(any(strcmp(report.runtime.engine, {'matlab', 'octave'})));
assert(~isempty(regexp(report.git_head, '^[0-9a-f]{40}$', 'once')));
assert(numel(report.implementation_source_hashes) >= 6);
assert(~isempty(regexp(report.implementation_source_digest, ...
    '^[0-9a-f]{64}$', 'once')));
assert(strcmp(report.semantic_payload.paper_level_status, ...
    'BLOCKED_SOURCE_BYTE_FREEZE_AND_STOCHASTIC_PROVENANCE'));
assert(strcmp(report.semantic_payload_sha256, ...
    '6f560ccd36492e9fb1c4057d67ea2e54fffa032e72ddd02557bad077aacaf502'));
parsed = jsondecode(fileread(report_path));
assert(strcmp(parsed.report_kind, 'EU26-05-INDEPENDENT-FIXTURE-v1'));
assert(strcmp(parsed.semantic_payload.protocol_id, ...
    'EU26-05-FORMULA-TRANSITION-v1'));
assert(numel(parsed.semantic_payload.probability_cases) == 5);
assert(numel(parsed.semantic_payload.decode_cases) == 4);
assert(numel(parsed.semantic_payload.transition_cases) == 4);
end

function result = complement(bits)
result = bits;
result(bits == '0') = '1';
result(bits == '1') = '0';
end

function assert_throws(callback, expected_identifier)
did_throw = false;
try
    callback();
catch exception
    did_throw = true;
    assert(strcmp(exception.identifier, expected_identifier));
end
assert(did_throw);
end

function delete_if_exists(path)
if exist(path, 'file') ~= 0
    delete(path);
end
end
