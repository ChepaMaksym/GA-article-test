function run_matlab_tests()
%RUN_MATLAB_TESTS Toolbox-free MATLAB/GNU Octave tests for USA26-01.

test_dir = fileparts(mfilename('fullpath'));
candidate_root = fileparts(fileparts(test_dir));
implementation_dir = fullfile(candidate_root, 'environments', 'matlab');
addpath(implementation_dir);
cleanup = onCleanup(@() rmpath(implementation_dir)); %#ok<NASGU>

test_benchmarks();
test_cross_environment_fixture(candidate_root);
test_properties_and_reproducibility();
test_evaluation_accounting();
test_validation();
fprintf('USA26-01 MATLAB/Octave tests: PASS\n');

    function test_benchmarks()
        zeros_population = zeros(3, 12);
        ones_population = ones(3, 12);
        assert(max(abs(gesmr_benchmark('sphere', zeros_population))) == 0);
        assert(max(abs(gesmr_benchmark('ackley', zeros_population))) < 1e-14);
        assert(max(abs(gesmr_benchmark('griewank', zeros_population))) == 0);
        assert(max(abs(gesmr_benchmark('rastrigin', zeros_population))) == 0);
        assert(max(abs(gesmr_benchmark('rosenbrock', ones_population))) == 0);
    end

    function test_cross_environment_fixture(root_dir)
        if exist('jsondecode', 'builtin') == 0 && exist('jsondecode', 'file') == 0
            error('gesmr:MissingJsonDecode', ...
                'jsondecode is required for the shared cross-environment fixture');
        end
        fixture_path = fullfile(root_dir, 'fixtures', 'cross_env_step.json');
        fixture = jsondecode(fileread(fixture_path));
        cfg = gesmr_default_config();
        names = fieldnames(fixture.config);
        for field_index = 1:numel(names)
            cfg.(names{field_index}) = fixture.config.(names{field_index});
        end
        result = gesmr_step( ...
            fixture.population, ...
            fixture.sigmas(:), ...
            fixture.objective, ...
            cfg, ...
            fixture.tape);
        tolerance = fixture.tolerance;
        assert(max(abs(result.next_population(:) ...
            - fixture.expected.next_population(:))) <= tolerance);
        assert(max(abs(result.next_fitness(:) ...
            - fixture.expected.next_fitness(:))) <= tolerance);
        assert(max(abs(result.group_delta(:) ...
            - fixture.expected.group_delta(:))) <= tolerance);
        assert(max(abs(result.next_sigmas(:) ...
            - fixture.expected.next_sigmas(:))) <= tolerance);
    end

    function test_properties_and_reproducibility()
        cfg = gesmr_default_config();
        cfg.non_elite_size = 20;
        cfg.n_groups = 4;
        first = run_gesmr('sphere', 12, 1, 7, 12, cfg);
        second = run_gesmr('sphere', 12, 1, 7, 12, cfg);
        assert(all(diff(first.best_fitness_history) <= 1e-12));
        assert(all(isfinite(first.sigma_history(:))));
        assert(all(first.sigma_history(:) > 0));
        assert(any(any(first.sigma_history(2:end, :) ...
            ~= first.sigma_history(1:end-1, :))));
        assert(isequal(first.final_population, second.final_population));
        assert(isequal(first.final_fitness, second.final_fitness));
        assert(isequal(first.sigma_history, second.sigma_history));
    end

    function test_evaluation_accounting()
        global GESMR_TEST_CALL_COUNT GESMR_TEST_ROW_COUNT
        cfg = gesmr_default_config();
        cfg.non_elite_size = 20;
        cfg.n_groups = 4;
        GESMR_TEST_CALL_COUNT = 0;
        GESMR_TEST_ROW_COUNT = 0;
        generations = 5;
        result = run_gesmr( ...
            @gesmr_test_counting_sphere, 12, 1, 0, generations, cfg);
        assert(GESMR_TEST_CALL_COUNT == generations + 1);
        assert(GESMR_TEST_ROW_COUNT ...
            == (cfg.non_elite_size + 1) * (generations + 1));
        assert(result.objective_call_count == GESMR_TEST_CALL_COUNT);
        assert(result.objective_row_evaluation_count == GESMR_TEST_ROW_COUNT);
        clear global GESMR_TEST_CALL_COUNT GESMR_TEST_ROW_COUNT
    end

    function test_validation()
        cfg = gesmr_default_config();
        cfg.non_elite_size = 20;
        cfg.n_groups = 3;
        did_throw = false;
        try
            gesmr_validate_config(cfg);
        catch
            did_throw = true;
        end
        assert(did_throw);
    end
end

function values = gesmr_test_counting_sphere(population)
global GESMR_TEST_CALL_COUNT GESMR_TEST_ROW_COUNT
GESMR_TEST_CALL_COUNT = GESMR_TEST_CALL_COUNT + 1;
GESMR_TEST_ROW_COUNT = GESMR_TEST_ROW_COUNT + size(population, 1);
values = sum(population .^ 2, 2);
end
