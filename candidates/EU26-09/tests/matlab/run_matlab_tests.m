function run_matlab_tests
% Independent MATLAB/Octave parser, formula, and claim-boundary checks.
test_directory = fileparts(mfilename('fullpath'));
candidate = fileparts(fileparts(test_directory));
matlab_environment = fullfile(candidate, 'environments', 'matlab');
addpath(matlab_environment);
checkout = getenv('EU2609_UPSTREAM');
if isempty(checkout)
    error('EU2609:Environment', 'EU2609_UPSTREAM is required');
end

checks = 0;
summary = eu2609_parse_artifact(checkout);
check(summary.run_count == 500, 'run count'); checks = checks + 1;
check(summary.generation_total == 98168, 'generation total'); checks = checks + 1;
check(summary.evaluation_total == 447632, 'evaluation total'); checks = checks + 1;
check(summary.fitness_total == 50000, 'fitness total'); checks = checks + 1;
check(summary.final_lambda_total == 4946, 'lambda total'); checks = checks + 1;
check(strcmp(summary.generation_mean, '196.336'), 'generation mean'); checks = checks + 1;
check(strcmp(summary.evaluation_mean, '895.264'), 'evaluation mean'); checks = checks + 1;
check(strcmp(summary.fitness_mean, '100.0'), 'fitness mean'); checks = checks + 1;
check(strcmp(summary.final_lambda_mean, '9.892'), 'lambda mean'); checks = checks + 1;
check(summary.all_solved, 'all solved'); checks = checks + 1;

check(eu2609_round_ties_even(1.5) == 2, 'odd half rounds up'); checks = checks + 1;
check(eu2609_round_ties_even(2.5) == 2, 'even half rounds down'); checks = checks + 1;
check(eu2609_round_ties_even(3.5) == 4, 'next odd half rounds up'); checks = checks + 1;
state = eu2609_controls(2.5, 100, 1.0);
check(state.source_offspring_count == 2, 'source offspring count'); checks = checks + 1;
check(state.paper_offspring_count == 3, 'paper offspring count'); checks = checks + 1;
check(abs(state.mutation_probability - 0.025) < 1e-15, 'mutation probability'); checks = checks + 1;
check(abs(state.crossover_probability - 0.4) < 1e-15, 'crossover probability'); checks = checks + 1;
check(state.evaluation_increment == 4, 'evaluation increment'); checks = checks + 1;
check(eu2609_transition(1.0, true, 1.5, 100) == 1.0, 'success floor'); checks = checks + 1;
check(abs(eu2609_transition(1.0, false, 1.5, 100) - 1.5^(1/4)) < 1e-12, ...
    'failure transition'); checks = checks + 1;
check(eu2609_transition(100.0, false, 1.5, 100) == 1.0, 'cap reset'); checks = checks + 1;
check(eu2609_transition(99.0, false, 1.5, 100) == 100.0, 'cap clamp'); checks = checks + 1;
must_fail(@() eu2609_round_ties_even(0)); checks = checks + 1;
must_fail(@() eu2609_controls(101, 100, 1)); checks = checks + 1;
must_fail(@() eu2609_transition(1, false, 1, 100)); checks = checks + 1;

report = struct();
report.schema_version = '1.0.0';
report.candidate_id = 'EU26-09';
report.status = 'PASS_MATLAB_OCTAVE_INDEPENDENT';
report.paper_mapping = 'PAPER_FIGURE_CONTEXT_ONLY';
report.assertions = checks;
report.totals = struct('generations', summary.generation_total, ...
    'evaluations', summary.evaluation_total, 'fitness', summary.fitness_total, ...
    'final_logged_lambda', summary.final_lambda_total);
report.means = struct('generations', summary.generation_mean, ...
    'evaluations', summary.evaluation_mean, 'fitness', summary.fitness_mean, ...
    'final_logged_lambda', summary.final_lambda_mean);
report.source_half_integer_count = state.source_offspring_count;
report.paper_half_integer_count = state.paper_offspring_count;
report.forbidden_claims = {'PASS_FULL', 'PASS_LITERAL_PAPER_ENDPOINT', ...
    'HISTORICAL_DEPENDENCY_ENVIRONMENT_PROVEN'};
output = getenv('EU2609_OCTAVE_REPORT');
if ~isempty(output)
    if exist(output, 'file')
        error('EU2609:Evidence', 'report output must be a new path');
    end
    file_id = fopen(output, 'w');
    if file_id < 0
        error('EU2609:Evidence', 'cannot create report output');
    end
    cleanup = onCleanup(@() fclose(file_id)); %#ok<NASGU>
    fprintf(file_id, '%s\n', jsonencode(report));
end
fprintf('EU26-09 MATLAB/Octave tests: %d assertions; PASS\n', checks);
end

function check(condition, label)
if ~condition
    error('EU2609:Test', 'assertion failed: %s', label);
end
end

function must_fail(action)
failed = false;
try
    action();
catch
    failed = true;
end
if ~failed
    error('EU2609:Test', 'expected failure was not raised');
end
end
