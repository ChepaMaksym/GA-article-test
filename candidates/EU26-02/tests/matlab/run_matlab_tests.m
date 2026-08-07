function run_matlab_tests()
%RUN_MATLAB_TESTS Toolbox-free MATLAB/GNU Octave Deleter tests for EU26-02.

test_dir = fileparts(mfilename('fullpath'));
candidate_root = fileparts(fileparts(test_dir));
implementation_dir = fullfile(candidate_root, 'environments', 'matlab');
addpath(implementation_dir);
cleanup = onCleanup(@() rmpath(implementation_dir)); %#ok<NASGU>

test_initialization();
test_shared_transition_cases(candidate_root);
test_lifetime_mean_and_warmup();
test_update_precedes_deletion();
test_deletion_cadence_tie_and_boundary();
test_invalid_inputs_fail_closed();
fprintf('EU26-02 MATLAB/Octave Deleter tests: PASS\n');

    function test_initialization()
        state = ahead_deleter_initial_state();
        assert(state.nb_operators == 6);
        assert(state.nb_selected == 2);
        assert(state.turn == 0);
        assert(isequal(state.possible_operators, 0:5));
        assert(isempty(state.removed_operators));
        assert(isequal(state.nb_times_used_total, zeros(1, 6)));
        assert(isequal(state.mean_score, zeros(1, 6)));
    end

    function test_shared_transition_cases(root_dir)
        require_jsondecode();
        fixture_path = fullfile( ...
            root_dir, 'fixtures', 'deleter_transition_cases.json');
        fixture = jsondecode(fileread(fixture_path));
        assert(strcmp(fixture.schema_version, '1.0.0'));
        assert(strcmp(fixture.frozen_source.source_commit, ...
            '04da9dd489f6e8e76fa3504d105c137bdf9ea323'));
        assert(strcmp(fixture.frozen_source.archive_sha256, ...
            ['1b7e8cf1ef637005bd994104f6e1ee520256ed387994b126b', ...
             'be875a137632e41']));
        cases = fixture.cases;
        for case_index = 1:numel(cases)
            test_case = struct_array_item(cases, case_index);
            state = ahead_deleter_initial_state();
            state.nb_operators = test_case.state.nb_operators;
            state.nb_selected = test_case.state.nb_selected;
            state.turn = test_case.state.turn;
            state.possible_operators = row(test_case.state.surviving);
            state.removed_operators = row(test_case.state.removed);
            state.nb_times_used_total = row(test_case.state.counts);
            state.mean_score = row(test_case.state.means);

            [next_state, event] = ahead_deleter_transition( ...
                state, row(test_case.selected_operators), ...
                row(test_case.scores));

            assert(event.source_turn == test_case.state.turn);
            assert(next_state.turn == test_case.expected_turn);
            assert(isequal(next_state.possible_operators, ...
                row(test_case.expected_surviving)));
            assert(isequal(next_state.nb_times_used_total, ...
                row(test_case.expected_counts)));
            assert(isequal(next_state.mean_score, ...
                row(test_case.expected_means)));
            expected_deleted = test_case.expected_deleted_operator;
            if is_json_null(expected_deleted)
                assert(~event.did_delete);
                assert(isempty(event.removed_operator));
                expected_removed = row(test_case.state.removed);
            else
                assert(event.did_delete);
                assert(event.removed_operator == expected_deleted);
                expected_removed = sort( ...
                    [row(test_case.state.removed), expected_deleted]);
            end
            assert(isequal(next_state.removed_operators, expected_removed));
        end
    end

    function test_lifetime_mean_and_warmup()
        state = ahead_deleter_initial_state();
        [state, event] = ahead_deleter_transition(state, [0, 0], [2, 4]);
        assert(~event.did_delete);
        assert(state.nb_times_used_total(1) == 2);
        assert(state.mean_score(1) == 3);

        % Finish source turns 1..29. Operator 0 remains the unique worst,
        % but warm-up prevents its premature deletion.
        for source_turn = 1:29
            assert(state.turn == source_turn);
            [state, event] = ahead_deleter_transition(state, [1, 2], [0, 0]);
            assert(~event.did_delete);
            assert(isequal(state.possible_operators, 0:5));
        end
        assert(state.turn == 30);

        [state, event] = ahead_deleter_transition(state, [1, 2], [0, 0]);
        assert(event.source_turn == 30);
        assert(event.did_delete);
        assert(event.removed_operator == 0);
        assert(~ismember(0, state.possible_operators));
    end

    function test_update_precedes_deletion()
        state = ahead_deleter_initial_state();
        state.turn = 30;
        state.nb_times_used_total = 10 * ones(1, 6);
        state.mean_score = [10, 9, 1, 1, 1, 1];

        % Operator 0 is worst before scoring, but its two zero-penalty
        % children reduce its lifetime mean below operator 1. The source
        % updates both scores first, so operator 1 must be deleted.
        [state, event] = ahead_deleter_transition(state, [0, 0], [0, 0]);
        assert(state.nb_times_used_total(1) == 12);
        assert(state.mean_score(1) == 100 / 12);
        assert(event.did_delete);
        assert(event.removed_operator == 1);
    end

    function test_deletion_cadence_tie_and_boundary()
        state = ahead_deleter_initial_state();
        deletion_turns = zeros(1, 0);
        deleted = zeros(1, 0);
        while state.turn <= 50
            first = state.possible_operators(1);
            last = state.possible_operators(end);
            [state, event] = ahead_deleter_transition( ...
                state, [first, last], [0, 0]);
            if event.did_delete
                deletion_turns(end + 1) = event.source_turn; %#ok<AGROW>
                deleted(end + 1) = event.removed_operator; %#ok<AGROW>
            end
        end
        assert(isequal(deletion_turns, [30, 35, 40, 45, 50]));
        % All means are tied at zero: ordered-source semantics remove the
        % lowest surviving identifier at every deletion event.
        assert(isequal(deleted, [0, 1, 2, 3, 4]));
        assert(isequal(state.possible_operators, 5));

        for step_index = 1:10
            [state, event] = ahead_deleter_transition(state, [5, 5], [0, 0]);
            assert(~event.did_delete);
            assert(isequal(state.possible_operators, 5));
        end
    end

    function test_invalid_inputs_fail_closed()
        state = ahead_deleter_initial_state();
        assert_throws(@() ahead_deleter_transition( ...
            state, [0], [1, 1]), 'EU2602:BadDeleterInput');
        assert_throws(@() ahead_deleter_transition( ...
            state, [0; 1], [1, 1]), 'EU2602:BadDeleterInput');
        assert_throws(@() ahead_deleter_transition( ...
            state, [0, 1], [1; 1]), 'EU2602:BadDeleterInput');
        assert_throws(@() ahead_deleter_transition( ...
            state, [0, 6], [1, 1]), 'EU2602:BadDeleterInput');
        assert_throws(@() ahead_deleter_transition( ...
            state, [0, 1], [1, Inf]), 'EU2602:BadDeleterInput');
        assert_throws(@() ahead_deleter_transition( ...
            state, [0, 1], [1, -1]), 'EU2602:BadDeleterInput');
        assert_throws(@() ahead_deleter_transition( ...
            state, [0, 1], [1, 1.5]), 'EU2602:BadDeleterInput');

        bad = state;
        bad.turn = -1;
        assert_throws(@() ahead_deleter_transition( ...
            bad, [0, 1], [1, 1]), 'EU2602:BadDeleterState');
        bad = state;
        bad.mean_score(1) = NaN;
        assert_throws(@() ahead_deleter_transition( ...
            bad, [0, 1], [1, 1]), 'EU2602:BadDeleterState');
        bad = state;
        bad.mean_score(1) = -1;
        bad.nb_times_used_total(1) = 1;
        assert_throws(@() ahead_deleter_transition( ...
            bad, [0, 1], [1, 1]), 'EU2602:BadDeleterState');
        bad = state;
        bad.nb_times_used_total(1) = 0.5;
        assert_throws(@() ahead_deleter_transition( ...
            bad, [0, 1], [1, 1]), 'EU2602:BadDeleterState');
        bad = state;
        bad.mean_score = zeros(2, 3);
        assert_throws(@() ahead_deleter_transition( ...
            bad, [0, 1], [1, 1]), 'EU2602:BadDeleterState');
        bad = state;
        bad.removed_operators = zeros(0, 1);
        assert_throws(@() ahead_deleter_transition( ...
            bad, [0, 1], [1, 1]), 'EU2602:BadDeleterState');
        bad = state;
        bad.possible_operators = (0:5)';
        assert_throws(@() ahead_deleter_transition( ...
            bad, [0, 1], [1, 1]), 'EU2602:BadDeleterState');
        bad = state;
        bad.possible_operators = [0, 2, 1, 3, 4, 5];
        assert_throws(@() ahead_deleter_transition( ...
            bad, [0, 1], [1, 1]), 'EU2602:BadDeleterState');

        removed = state;
        removed.turn = 31;
        removed.possible_operators = 1:5;
        removed.removed_operators = 0;
        assert_throws(@() ahead_deleter_transition( ...
            removed, [0, 1], [1, 1]), 'EU2602:BadDeleterInput');
    end
end

function require_jsondecode()
if exist('jsondecode', 'builtin') == 0 && exist('jsondecode', 'file') == 0
    error('EU2602:MissingJsonDecode', ...
        'jsondecode is required for the shared transition fixture');
end
end

function values = row(values)
values = reshape(values, 1, []);
end

function value = struct_array_item(values, index)
if iscell(values)
    value = values{index};
else
    value = values(index);
end
end

function tf = is_json_null(value)
tf = isempty(value) ...
    || (isnumeric(value) && isscalar(value) && isnan(value));
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
