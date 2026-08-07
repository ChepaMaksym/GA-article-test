function run_matlab_tests
%RUN_MATLAB_TESTS Independent MATLAB/GNU Octave fixed-tape verification.

test_dir = fileparts(mfilename('fullpath'));
candidate_dir = fileparts(fileparts(test_dir));
addpath(fullfile(candidate_dir, 'environments', 'matlab'));
fixture_path = fullfile(candidate_dir, 'fixtures', 'tworate_fixed_tape.json');
fixture = jsondecode(fileread(fixture_path));

assert(isequal(eu26_oneminmax([1 0 1 1]), [3 1]));
assert(eu26_hypervolume2d([50 50], [-1 -1]) == 2601);
assert(eu26_hypervolume2d([49 51; 50 50], [-1 -1]) == 2651);
assert(eu26_hypervolume2d([50 50; 49 51; 49 51], [-1 -1]) == 2651);
assert(eu26_hypervolume2d([50 50; 49 51], [-1 -1]) == ...
    eu26_hypervolume2d([49 51; 50 50], [-1 -1]));

adaptation_cases = fixture.adaptation_cases;
for i = 1:numel(adaptation_cases)
    entry = adaptation_cases(i);
    actual = eu26_tworate_adapt(entry.population, entry.children, ...
        entry.r, entry.q, entry.n);
    expected = entry.expected;
    assert(isequal(actual.scores(:), expected.scores(:)));
    assert(actual.winner_index == expected.winner_index);
    assert(strcmp(actual.winner_group, expected.winner_group));
    assert(actual.s == eu26_fraction(expected.s));
    assert(actual.q == eu26_fraction(expected.q));
    assert(strcmp(actual.decision, expected.decision));
    assert(actual.r_before == eu26_fraction(expected.r_before));
    assert(actual.r_after == eu26_fraction(expected.r_after));
end

generation_cases = fixture.generation_cases;
for i = 1:numel(generation_cases)
    entry = generation_cases(i);
    actual = eu26_generation_from_tape(entry);
    expected = entry.expected;
    assert(actual.n == expected.n && actual.lambda == expected.lambda);
    assert(isequal(actual.population_points_before, expected.population_points_before));
    assert(isequal(actual.parent_indices(:), expected.parent_indices(:)));
    expected_rates = cellfun(@eu26_fraction, normalize_cell(expected.mutation_probabilities));
    assert(max(abs(actual.mutation_probabilities(:) - expected_rates(:))) == 0);
    assert(isequal(actual.positive_binomial_counts(:), expected.positive_binomial_counts(:)));
    assert(isequal(actual.child_points, expected.child_points));
    assert(isequal(actual.adaptation.scores(:), expected.adaptation.scores(:)));
    assert(actual.adaptation.winner_index == expected.adaptation.winner_index);
    assert(strcmp(actual.adaptation.winner_group, expected.adaptation.winner_group));
    assert(actual.adaptation.s == eu26_fraction(expected.adaptation.s));
    assert(actual.adaptation.q == eu26_fraction(expected.adaptation.q));
    assert(actual.adaptation.r_after == eu26_fraction(expected.adaptation.r_after));
    assert(isequal(actual.population_points_after, expected.population_points_after));
    assert(actual.hypervolume_after == expected.hypervolume_after);
end

invalid_cases = fixture.invalid_generation_cases;
for i = 1:numel(invalid_cases)
    if iscell(invalid_cases)
        entry = invalid_cases{i};
    else
        entry = invalid_cases(i);
    end
    names = fieldnames(entry);
    input_fields = setdiff(names, {'case_id'; 'expected_error'});
    assert(numel(names) == 3 && numel(input_fields) == 1, ...
        ['invalid fixture schema changed: ' entry.case_id]);
    case_data = entry.(input_fields{1});
    accepted = true;
    message = '';
    try
        eu26_generation_from_tape(case_data);
    catch caught
        accepted = false;
        message = caught.message;
    end
    assert(~accepted, ['invalid fixture accepted: ' entry.case_id]);
    assert(~isempty(strfind(message, entry.expected_error)), ...
        ['unexpected invalid-fixture error: ' entry.case_id ...
         '; expected substring: ' entry.expected_error '; actual: ' message]); %#ok<STREMP>
end

rejected = false;
try
    eu26_hypervolume2d([0 0], [1 1]);
catch
    rejected = true;
end
assert(rejected, 'invalid HV reference must fail closed');

fprintf('EU26-01 MATLAB/Octave formula and fixed-tape tests: PASS\n');
end

function result = normalize_cell(value)
if iscell(value)
    result = value;
elseif isstring(value)
    result = cellstr(value);
elseif isnumeric(value)
    result = num2cell(value);
else
    error('EU26:Fixture', 'cannot normalize fixture rational list');
end
end
