function run_matlab_tests()
%RUN_MATLAB_TESTS Toolbox-free MATLAB/GNU Octave tests for EU26-07.

test_dir = fileparts(mfilename('fullpath'));
candidate_root = fileparts(fileparts(test_dir));
implementation_dir = fullfile(candidate_root, 'environments', 'matlab');
addpath(implementation_dir);
cleanup = onCleanup(@() rmpath(implementation_dir)); %#ok<NASGU>
fixture_path = fullfile(candidate_root, 'fixtures', 'fixed_tape_cases.json');
fixed_tape_fixture = jsondecode(fileread(fixture_path));

test_jump_fitness();
test_exact_mutation_and_crossover(fixed_tape_fixture);
test_named_rounding_profiles();
test_algorithm_controls();
test_lambda_update_and_reset_delay();
test_fixed_tape_profile_isolation(fixed_tape_fixture);
test_fixed_tape_acceptance_and_accounting();
test_invalid_inputs_fail_closed();
fprintf('EU26-07 MATLAB/Octave formula tests: PASS\n');

    function test_jump_fitness()
        n = 20;
        k = 4;
        [value, solved] = eu2607_jump_fitness(2 ^ n - 1, n, k);
        assert(value == 24);
        assert(solved);

        [value, solved] = eu2607_jump_fitness(2 ^ (n - k) - 1, n, k);
        assert(value == 20);
        assert(~solved);

        [value, solved] = eu2607_jump_fitness(2 ^ (n - k + 1) - 1, n, k);
        assert(value == 3);
        assert(~solved);
        assert(eu2607_jump_fitness(0, n, k) == 4);
    end

    function test_exact_mutation_and_crossover(fixture)
        operator = fixture.operator_case;
        mutant = eu2607_mutate_exact( ...
            operator.parent, operator.n, ...
            operator.mutation_positions_zero_based_lsb);
        assert(mutant == operator.expected_mutant);
        child = eu2607_crossover_mask( ...
            operator.parent, mutant, operator.n, ...
            operator.crossover_take_mutant_positions_zero_based_lsb);
        assert(child == operator.expected_crossover);
        assert(eu2607_mutate_exact(7, 20, []) == 7);
        assert(eu2607_crossover_mask(7, 8, 20, []) == 7);
    end

    function test_named_rounding_profiles()
        % The exact-half witness is a mandatory paper/artifact separator.
        assert(eu2607_round_lambda(2.5, 'paper_algorithm3') == 3);
        assert(eu2607_round_lambda(2.5, 'artifact_generic') == 2);
        assert(eu2607_round_lambda(2.5, ...
            'artifact_jump_optimized') == 2);
        assert(eu2607_round_lambda(3.5, 'artifact_generic') == 4);
        assert(eu2607_round_lambda(2.49, 'paper_algorithm3') == 2);
        assert(eu2607_round_lambda(2.51, 'artifact_generic') == 3);
    end

    function test_algorithm_controls()
        value = eu2607_controls(2.5, 20, 'paper_algorithm3', 1.0);
        assert(value.offspring_count == 3);
        assert(value.mutation_probability == 0.125);
        assert(value.crossover_probability == 0.4);
        assert_throws(@() eu2607_controls(2.5, 20, ...
            'paper_algorithm3', 0.5), 'EU2607:BadCrossoverCoefficient');
        assert_throws(@() eu2607_controls(true, 20, ...
            'paper_algorithm3', 1.0), 'EU2607:BadLambda');
    end

    function test_lambda_update_and_reset_delay()
        factor = 1.5;
        cap = 20;
        shrunk = eu2607_update_lambda(3, true, factor, cap, true);
        assert(abs(shrunk - 2) < 1e-15);
        assert(eu2607_update_lambda(1, true, factor, cap, true) == 1);

        % Reaching the cap by clamping is growth, not a same-step reset.
        reached_cap = eu2607_update_lambda(19, false, factor, cap, true);
        assert(reached_cap == cap);
        reset_after_later_failure = eu2607_update_lambda( ...
            reached_cap, false, factor, cap, true);
        assert(reset_after_later_failure == 1);

        no_reset = eu2607_update_lambda(cap, false, factor, cap, false);
        assert(no_reset == cap);
        success_at_cap = eu2607_update_lambda(cap, true, factor, cap, true);
        assert(abs(success_at_cap - cap / factor) < 1e-15);
    end

    function test_fixed_tape_profile_isolation(fixture)
        % Shared H7 witness: parent=1023 has ten ones and fitness 14.  Both
        % mutants and the non-parent crossover have eleven ones and fitness
        % 15.  At final tie index 1, the paper pool chooses its duplicated
        % selected mutant 2047, whereas either all-mutant artifact pool
        % chooses the otherwise unselected mutant 3071.
        assert(fixture.schema_version == 1);
        assert(numel(fixture.cases) == 2);
        paper_case = fixture.cases(1);
        artifact_case = fixture.cases(2);
        paper = run_fixed_tape_case(paper_case);
        generic = run_fixed_tape_case(artifact_case);
        optimized = eu2607_fixed_tape_generation( ...
            artifact_case.parent, artifact_case.n, artifact_case.k, ...
            artifact_case.lambda_real, artifact_case.update_factor, ...
            'artifact_jump_optimized', artifact_case.mutation_children, ...
            artifact_case.crossover_children, ...
            artifact_case.mutation_tie_choice, ...
            artifact_case.final_tie_choice);

        assert(strcmp(paper.profile, 'paper_algorithm3'));
        assert(isequal(paper.final_pool, [2047, 2047]));
        assert(paper.selected_mutant == paper_case.expected.selected_mutant);
        assert(paper.selected_candidate == ...
            paper_case.expected.selected_candidate);
        assert(paper.parent_after == paper_case.expected.parent_after);
        assert(paper.strict_success == paper_case.expected.strict_success);
        assert(paper.logical_evaluations == ...
            paper_case.expected.logical_evaluations);

        assert(isequal(generic.final_pool, [2047, 3071, 2047]));
        assert(generic.selected_mutant == ...
            artifact_case.expected.selected_mutant);
        assert(generic.selected_candidate == ...
            artifact_case.expected.selected_candidate);
        assert(generic.parent_after == artifact_case.expected.parent_after);
        assert(generic.strict_success == ...
            artifact_case.expected.strict_success);
        assert(generic.logical_evaluations == ...
            artifact_case.expected.logical_evaluations);
        assert(isequal(generic.final_pool, optimized.final_pool));
        assert(generic.selected_candidate == optimized.selected_candidate);
    end

    function test_fixed_tape_acceptance_and_accounting()
        neutral = eu2607_fixed_tape_generation( ...
            3, 20, 4, 2, 1.5, 'artifact_generic', ...
            [5, 1], [3, 1], 0, 0);
        assert(~neutral.strict_success);
        assert(neutral.parent_after == 5);
        assert(neutral.logical_evaluations == 4);
        assert(neutral.lambda_after > neutral.lambda_before);

        worse = eu2607_fixed_tape_generation( ...
            3, 20, 4, 2, 1.5, 'paper_algorithm3', ...
            [1, 1], [1, 1], 0, 0);
        assert(~worse.strict_success);
        assert(worse.selected_candidate == 1);
        assert(worse.parent_after == 3);
        assert(worse.logical_evaluations == 4);

        all_parent = eu2607_fixed_tape_generation( ...
            3, 20, 4, 2, 1.5, 'artifact_jump_optimized', ...
            [3, 3], [3, 3], 0, 999);
        assert(isempty(all_parent.final_pool));
        assert(all_parent.selected_candidate == 3);
        assert(all_parent.parent_after == 3);
    end

    function test_invalid_inputs_fail_closed()
        assert_throws(@() eu2607_jump_fitness(0, 10, 4), ...
            'EU2607:BadProblem');
        assert_throws(@() eu2607_jump_fitness(0, 20, 20), ...
            'EU2607:BadProblem');
        assert_throws(@() eu2607_jump_fitness(2 ^ 20, 20, 4), ...
            'EU2607:BadBitString');
        assert_throws(@() eu2607_round_lambda(2, 'paper'), ...
            'EU2607:BadProfile');
        assert_throws(@() eu2607_round_lambda(0.9, 'paper_algorithm3'), ...
            'EU2607:BadLambda');
        assert_throws(@() eu2607_update_lambda(2, 1, 1.5, 20, true), ...
            'EU2607:BadSuccessFlag');
        assert_throws(@() eu2607_update_lambda(2, false, 1, 20, true), ...
            'EU2607:BadUpdateFactor');
        assert_throws(@() eu2607_update_lambda(21, false, 1.5, 20, true), ...
            'EU2607:BadLambda');
        assert_throws(@() eu2607_fixed_tape_generation( ...
            1, 20, 4, 2, 1.5, 'artifact_generic', ...
            [3], [6, 1], 0, 0), 'EU2607:BadTape');
        assert_throws(@() eu2607_fixed_tape_generation( ...
            1, 20, 4, 2, 1.5, 'artifact_generic', ...
            [3, 5.5], [6, 1], 0, 0), 'EU2607:BadTape');
        assert_throws(@() eu2607_fixed_tape_generation( ...
            1, 20, 4, 2, 1.5, 'artifact_generic', ...
            [3, 5], [6, 1], 2, 0), 'EU2607:BadTieChoice');
        assert_throws(@() eu2607_mutate_exact(0, 20, [1, 1]), ...
            'EU2607:BadPositions');
        assert_throws(@() eu2607_crossover_mask(0, 1, 20, 20), ...
            'EU2607:BadPositions');
    end
end

function result = run_fixed_tape_case(case_value)
result = eu2607_fixed_tape_generation( ...
    case_value.parent, case_value.n, case_value.k, ...
    case_value.lambda_real, case_value.update_factor, case_value.profile, ...
    case_value.mutation_children, case_value.crossover_children, ...
    case_value.mutation_tie_choice, case_value.final_tie_choice);
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
