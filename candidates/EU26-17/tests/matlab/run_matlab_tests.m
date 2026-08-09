function run_matlab_tests()
%RUN_MATLAB_TESTS Toolbox-free MATLAB/GNU Octave tests for EU26-17.

test_dir = fileparts(mfilename('fullpath'));
candidate_root = fileparts(fileparts(test_dir));
implementation_dir = fullfile(candidate_root, 'environments', 'matlab');
addpath(implementation_dir);
cleanup = onCleanup(@() rmpath(implementation_dir)); %#ok<NASGU>

test_shared_fixture(candidate_root);
test_threshold_equalities();
test_repeated_bounds();
test_fail_closed_validation();
fprintf(['EU26-17 MATLAB/Octave source-transition tests: PASS; ' ...
    'eligibility remains HARD_FAIL\n']);

    function test_shared_fixture(root_dir)
        require_jsondecode();
        fixture_path = fullfile(root_dir, 'fixtures', 'transition_cases.json');
        fixture = jsondecode(fileread(fixture_path));
        tolerance = fixture.tolerance;
        for index = 1:numel(fixture.cases)
            item = case_at(fixture.cases, index);
            result = eu2617_transition(item.fitness, item.state, fixture.config);
            assert(abs(result.gdm - item.expected.gdm) <= tolerance);
            assert(abs(result.current.mutation_rate ...
                - item.expected.mutation_rate) <= tolerance);
            assert(abs(result.current.crossover_rate ...
                - item.expected.crossover_rate) <= tolerance);
            assert(strcmp(result.branch, item.expected.branch));
        end
    end

    function test_threshold_equalities()
        cfg = eu2617_default_config();
        state = struct('mutation_rate', 0.025, 'crossover_rate', 0.75);

        at_min = zeros(200, 1);
        at_min(1) = 1;
        min_result = eu2617_transition(at_min, state, cfg);
        assert(min_result.gdm == cfg.v_min);
        assert(strcmp(min_result.branch, 'no_change'));
        assert(min_result.current.mutation_rate == state.mutation_rate);
        assert(min_result.current.crossover_rate == state.crossover_rate);

        at_max = zeros(20, 1);
        at_max(1:3) = 1;
        max_result = eu2617_transition(at_max, state, cfg);
        assert(max_result.gdm == cfg.v_max);
        assert(strcmp(max_result.branch, 'no_change'));
        assert(max_result.current.mutation_rate == state.mutation_rate);
        assert(max_result.current.crossover_rate == state.crossover_rate);
    end

    function test_repeated_bounds()
        cfg = eu2617_default_config();
        state = struct('mutation_rate', 0.025, 'crossover_rate', 0.75);
        for index = 1:100
            result = eu2617_transition([1, 1], state, cfg);
            state = result.current;
        end
        assert(state.mutation_rate == cfg.mutation_rate_max);
        assert(state.crossover_rate == cfg.crossover_rate_min);

        for index = 1:200
            result = eu2617_transition([-0.999, 1], state, cfg);
            state = result.current;
        end
        assert(state.mutation_rate == cfg.mutation_rate_min);
        assert(state.crossover_rate == cfg.crossover_rate_max);
    end

    function test_fail_closed_validation()
        cfg = eu2617_default_config();
        state = struct('mutation_rate', 0.025, 'crossover_rate', 0.75);
        must_throw(@() eu2617_transition([], state, cfg));
        must_throw(@() eu2617_transition([NaN, 1], state, cfg));
        must_throw(@() eu2617_transition([Inf, 1], state, cfg));
        must_throw(@() eu2617_transition([0, 0], state, cfg));
        must_throw(@() eu2617_transition([-1, 0], state, cfg));
        must_throw(@() eu2617_transition([1, 1], ...
            struct('mutation_rate', 0.3, 'crossover_rate', 0.75), cfg));
        bad_cfg = cfg;
        bad_cfg.v_min = bad_cfg.v_max;
        must_throw(@() eu2617_transition([1, 1], state, bad_cfg));
        bad_cfg = cfg;
        bad_cfg.mutation_rate_multiplier = 1;
        must_throw(@() eu2617_transition([1, 1], state, bad_cfg));
    end
end

function require_jsondecode()
if exist('jsondecode', 'builtin') == 0 && exist('jsondecode', 'file') == 0
    error('eu2617:MissingJsonDecode', 'jsondecode is required for fixture tests');
end
end

function must_throw(operation)
did_throw = false;
try
    operation();
catch
    did_throw = true;
end
assert(did_throw);
end

function item = case_at(cases, index)
if iscell(cases)
    item = cases{index};
else
    item = cases(index);
end
end
