function run_matlab_tests()
%RUN_MATLAB_TESTS Toolbox-free USA26-04 formula/ambiguity tests.

test_dir = fileparts(mfilename('fullpath'));
candidate_root = fileparts(fileparts(test_dir));
implementation_dir = fullfile(candidate_root, 'environments', 'matlab');
addpath(implementation_dir);
cleanup = onCleanup(@() rmpath(implementation_dir)); %#ok<NASGU>

oracles = jsondecode(fileread(fullfile( ...
    candidate_root, 'fixtures', 'formula_oracles.json')));
fixture = jsondecode(fileread(fullfile( ...
    candidate_root, 'fixtures', 'fixed_controller_tape.json')));
tolerance = oracles.tolerance.absolute;

test_objectives(oracles, tolerance);
test_rewards(oracles, tolerance);
test_update(oracles, tolerance);
test_ambiguities();
test_fixed_tape(fixture, tolerance);
test_provenance_report();
test_adversarial_rejection();
fprintf(['USA26-04 MATLAB/Octave formula tests: PASS; ' ...
    'paper status remains BLOCKED_G5_G9 / INCONCLUSIVE_PUBLISHED_RESULT\n']);

    function test_objectives(data, tol)
        zero = data.objective_anchors.zero5.vector;
        one = data.objective_anchors.one5.vector;
        mixed = data.objective_anchors.mixed5.vector;
        names = {'ackley', 'griewank', 'rastrigin', 'sphere', 'linear'};
        for index = 1:numel(names)
            name = names{index};
            assert(abs(bandit_objective(name, zero) ...
                - data.objective_anchors.zero5.expected.(name)) <= tol);
            expected = data.objective_anchors.mixed5.expected.(name);
            actual = bandit_objective(name, mixed);
            assert(abs(actual - expected) <= tol + tol * abs(expected));
        end
        assert(bandit_objective('rosenbrock', one) == 0);
        expected = data.objective_anchors.mixed5.expected.rosenbrock;
        assert(abs(bandit_objective('rosenbrock', mixed) - expected) <= tol);
    end

    function test_rewards(data, tol)
        parent = data.reward_sign.parent;
        child = data.reward_sign.child;
        names = {'P1', 'P2', 'P3'};
        for index = 1:numel(names)
            name = names{index};
            assert(abs(bandit_reward(name, parent, child) ...
                - data.reward_sign.expected.(name)) <= tol);
        end
        assert(bandit_reward('P2', parent, child) > 0);
        assert(bandit_reward('P3', parent, child) < 0);
        did_throw = false;
        try
            bandit_printed_eq2_literal(parent, child);
        catch exception
            did_throw = strcmp(exception.identifier, ...
                'banditverify:PrintedEq2Singular');
        end
        assert(did_throw);
    end

    function test_update(data, tol)
        input = data.nesterov;
        actual = bandit_nesterov_update( ...
            input.value, input.momentum, input.reward, ...
            input.learning_rate, input.momentum_factor);
        assert(abs(actual.gradient - input.expected_gradient) <= tol);
        assert(abs(actual.momentum - input.expected_momentum) <= tol);
        assert(abs(actual.value - input.expected_value) <= tol);
        opposite = bandit_nesterov_update(0, 0, -1, 0.001, 0.9);
        assert(abs(opposite.value + 0.0038) <= tol);
    end

    function test_ambiguities()
        witness = bandit_ambiguity_witnesses();
        assert(strcmp(witness.boundary.status, 'AMBIGUITY_CONFIRMED'));
        assert(~witness.boundary.resolution_chosen);
        assert(witness.boundary.floor_tile_count == 6666);
        assert(witness.boundary.uncovered_width_if_clamped > 0);
        assert(witness.boundary.overshoot_width_if_next_tile > 0);
        assert(strcmp(witness.tie.status, 'AMBIGUITY_CONFIRMED'));
        assert(isempty(witness.tie.selected_tile));
        assert(witness.standard_deviation.all_distinct_at_1e_3);
        assert(strcmp(witness.paper_level_status, 'BLOCKED_G5_G9'));
    end

    function test_fixed_tape(data, tol)
        actual = bandit_run_fixed_tape(data);
        expected = data.expected;
        assert(strcmp(actual.state_provenance, ...
            'synthetic_fixture_not_article_state'));
        assert(strcmp(actual.paper_level_status, 'BLOCKED_G5_G9'));
        assert(strcmp(actual.published_result_status, ...
            'INCONCLUSIVE_PUBLISHED_RESULT'));
        assert(max(abs(actual.base_weights(:) ...
            - expected.base_weights(:))) <= tol);
        assert(strcmp(actual.branch, expected.branch));
        assert(actual.argmax_tile == expected.argmax_tile);
        assert(actual.selected_tile == expected.selected_tile);
        assert(abs(actual.log_rate - expected.log_rate) <= tol);
        assert(abs(actual.rate - expected.rate) <= tol);
        assert(abs(actual.immediate_reward - expected.immediate_reward) <= tol);
        for index = 1:numel(actual.updates)
            keys = {'paper_index', 'max_reward', 'gradient', 'momentum', 'value'};
            for key_index = 1:numel(keys)
                key = keys{key_index};
                assert(abs(actual.updates(index).(key) ...
                    - expected.updates(index).(key)) <= tol);
            end
            assert(max(abs(actual.updates(index).history(:) ...
                - expected.updates(index).history(:))) <= tol);
        end
    end

    function test_adversarial_rejection()
        assert_throws(@() bandit_objective('sphere', [0, Inf]));
        assert_throws(@() bandit_objective('rosenbrock', 1));
        assert_throws(@() bandit_reward('P2', [-2], [0]));
        assert_throws(@() bandit_reward('P4', [1], [0]));
        assert_throws(@() bandit_tile_index(0, -1, 0, 0));
        assert_throws(@() bandit_nesterov_update(0, 0, 1, 0, 0.9));
    end

    function test_provenance_report()
        report_path = [tempname '.json'];
        report_cleanup = onCleanup(@() delete_if_present(report_path)); %#ok<NASGU>
        write_fixed_tape_report(report_path);
        report = jsondecode(fileread(report_path));
        assert(strcmp(report.schema_version, ...
            'USA26-04-MATLAB-H2-REPORT-v1'));
        assert(strcmp(report.protocol_id, ...
            'USA26-04-FORMULA-PORTABILITY-v1'));
        assert(~isempty(regexp(report.git_sha, '^[0-9a-f]{40}$', 'once')));
        assert(any(strcmp(report.engine.name, {'GNU Octave', 'MATLAB'})));
        assert(~isempty(report.engine.version));
        assert(numel(report.matlab_sources) == 8);
        source_paths = {report.matlab_sources.path};
        assert(numel(unique(source_paths)) == 8);
        for source_index = 1:numel(report.matlab_sources)
            assert(~isempty(regexp(report.matlab_sources(source_index).sha256, ...
                '^[0-9a-f]{64}$', 'once')));
        end
        assert(strcmp(report.fixture_path, ...
            'fixtures/fixed_controller_tape.json'));
        assert(~isempty(regexp(report.fixture_sha256, ...
            '^[0-9a-f]{64}$', 'once')));
        assert(~isempty(regexp(report.canonical_payload_sha256, ...
            '^[0-9a-f]{64}$', 'once')));
        assert(strcmp(report.payload.state_provenance, ...
            'synthetic_fixture_not_article_state'));
    end

    function delete_if_present(path)
        if exist(path, 'file') ~= 0
            delete(path);
        end
    end

    function assert_throws(action)
        did_throw = false;
        try
            action();
        catch
            did_throw = true;
        end
        assert(did_throw);
    end
end
