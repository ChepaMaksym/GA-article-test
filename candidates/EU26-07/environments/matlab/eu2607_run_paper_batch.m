function report = eu2607_run_paper_batch(config)
%EU2607_RUN_PAPER_BATCH Execute independent Algorithm 3 runs and summarize them.
%
% This helper is intended for paper-profile experiments. Seeds are explicitly
% auditor-defined unless a separate provenance record binds them to an author
% ledger. It never compares these trajectories with the Python artifact
% profile because the two profiles have different rounding and selection
% semantics.
%
% CONFIG fields:
%   n, k, update_factor, max_generations, max_evaluations
%       forwarded to eu2607_run_paper_algorithm3
%   runs             positive integer                     (default 500)
%   base_seed         non-negative integer                 (default 1)
%   output_csv        optional output path                 (default '')
%
% Run r uses effective seed base_seed+r, matching the explicit seed-addressed
% convention used elsewhere in the candidate while retaining a distinct claim
% boundary for this independently selected seed ledger.

if nargin < 1
    config = struct();
end
config = normalize_batch_config(config);

run_numbers = (1:config.runs)';
seeds = zeros(config.runs, 1);
generations = zeros(config.runs, 1);
evaluations = zeros(config.runs, 1);
final_fitness = zeros(config.runs, 1);
final_lambda = zeros(config.runs, 1);
solved = false(config.runs, 1);
statuses = cell(config.runs, 1);

for run_index = 1:config.runs
    run_config = struct();
    run_config.n = config.n;
    run_config.k = config.k;
    run_config.update_factor = config.update_factor;
    run_config.seed = config.base_seed + run_index;
    run_config.max_generations = config.max_generations;
    run_config.max_evaluations = config.max_evaluations;
    run_config.record_trace = false;
    one_run = eu2607_run_paper_algorithm3(run_config);

    seeds(run_index) = one_run.seed;
    generations(run_index) = one_run.generations;
    evaluations(run_index) = one_run.logical_evaluations;
    final_fitness(run_index) = one_run.final_fitness;
    final_lambda(run_index) = one_run.lambda_final;
    solved(run_index) = one_run.solved;
    statuses{run_index} = one_run.status;
end

rows = struct();
rows.run = run_numbers;
rows.effective_seed = seeds;
rows.generations = generations;
rows.logical_evaluations = evaluations;
rows.final_fitness = final_fitness;
rows.final_lambda = final_lambda;
rows.solved = solved;
rows.status = statuses;

summary = struct();
summary.runs = config.runs;
summary.solved_runs = sum(solved);
summary.incomplete_runs = config.runs - summary.solved_runs;
if all(solved)
    summary.status = 'PASS_ALL_RUNS_SOLVED';
    summary.mean_evaluations = mean(evaluations);
    summary.median_evaluations = median(evaluations);
    summary.q10_evaluations = linear_quantile(evaluations, 0.10);
    summary.q25_evaluations = linear_quantile(evaluations, 0.25);
    summary.q75_evaluations = linear_quantile(evaluations, 0.75);
    summary.q90_evaluations = linear_quantile(evaluations, 0.90);
    summary.population_sd_evaluations = std(evaluations, 1);
    if config.runs >= 2
        summary.sample_sd_evaluations = std(evaluations, 0);
    else
        summary.sample_sd_evaluations = NaN;
    end
else
    summary.status = 'INCOMPLETE_RUNS_NO_UNQUALIFIED_AGGREGATE';
    summary.mean_evaluations = NaN;
    summary.median_evaluations = NaN;
    summary.q10_evaluations = NaN;
    summary.q25_evaluations = NaN;
    summary.q75_evaluations = NaN;
    summary.q90_evaluations = NaN;
    summary.population_sd_evaluations = NaN;
    summary.sample_sd_evaluations = NaN;
end

report = struct();
report.schema_version = 1;
report.profile = 'paper_algorithm3_fixed_order';
report.seed_protocol = 'auditor_defined_base_plus_run';
report.configuration = struct( ...
    'n', config.n, ...
    'k', config.k, ...
    'update_factor', config.update_factor, ...
    'lambda_max', config.n, ...
    'runs', config.runs, ...
    'base_seed', config.base_seed, ...
    'max_generations', config.max_generations, ...
    'max_evaluations', config.max_evaluations);
report.rows = rows;
report.summary = summary;
report.claim_boundary = [ ...
    'Independent MATLAB paper-profile experiment. Seed identity and runtime ', ...
    'environment must be frozen before any published-result comparison.'];

if ~isempty(config.output_csv)
    write_rows_csv(config.output_csv, rows);
end
end

function config = normalize_batch_config(config)
if ~isstruct(config) || ~isscalar(config)
    error('EU2607:BadConfig', 'config must be a scalar struct');
end
config.n = field_or_default(config, 'n', 20);
config.k = field_or_default(config, 'k', 4);
config.update_factor = field_or_default(config, 'update_factor', 1.5);
config.max_generations = field_or_default(config, 'max_generations', Inf);
config.max_evaluations = field_or_default(config, 'max_evaluations', Inf);
config.runs = field_or_default(config, 'runs', 500);
config.base_seed = field_or_default(config, 'base_seed', 1);
config.output_csv = field_or_default(config, 'output_csv', '');

if ~is_scalar_integer(config.n) || config.n < 11
    error('EU2607:BadProblem', 'n must be an integer >= 11');
end
if ~is_scalar_integer(config.k) || config.k < 1 || config.k >= config.n
    error('EU2607:BadProblem', 'k must be an integer in [1,n)');
end
if ~is_scalar_real(config.update_factor) || config.update_factor <= 1
    error('EU2607:BadUpdateFactor', 'update_factor must be finite and > 1');
end
if ~is_scalar_integer(config.runs) || config.runs < 1
    error('EU2607:BadConfig', 'runs must be a positive integer');
end
if ~is_scalar_integer(config.base_seed) || config.base_seed < 0
    error('EU2607:BadSeed', 'base_seed must be a non-negative integer');
end
validate_limit(config.max_generations, 'max_generations', false);
validate_limit(config.max_evaluations, 'max_evaluations', true);
if ischar(config.output_csv) && isrow(config.output_csv)
    % Valid path representation for MATLAB and GNU Octave.
elseif has_isstring() && isstring(config.output_csv) && isscalar(config.output_csv)
    config.output_csv = char(config.output_csv);
else
    error('EU2607:BadConfig', 'output_csv must be a character row or scalar string');
end

config.n = double(config.n);
config.k = double(config.k);
config.update_factor = double(config.update_factor);
config.max_generations = double(config.max_generations);
config.max_evaluations = double(config.max_evaluations);
config.runs = double(config.runs);
config.base_seed = double(config.base_seed);
end

function value = field_or_default(config, name, default_value)
if isfield(config, name)
    value = config.(name);
else
    value = default_value;
end
end

function validate_limit(value, name, allow_zero)
if isnumeric(value) && ~islogical(value) && isreal(value) && isscalar(value) ...
        && isinf(double(value)) && double(value) > 0
    return;
end
minimum = 1;
if allow_zero
    minimum = 0;
end
if ~is_scalar_integer(value) || value < minimum
    error('EU2607:BadConfig', ...
        '%s must be an integer >= %d or positive Inf', name, minimum);
end
end

function value = linear_quantile(values, probability)
ordered = sort(reshape(double(values), [], 1));
if isempty(ordered)
    error('EU2607:EmptyAggregate', 'cannot aggregate an empty run set');
end
position = (numel(ordered) - 1) * probability + 1;
lower = floor(position);
upper = ceil(position);
if lower == upper
    value = ordered(lower);
else
    fraction = position - lower;
    value = ordered(lower) + fraction * (ordered(upper) - ordered(lower));
end
end

function write_rows_csv(path, rows)
[file_id, message] = fopen(path, 'w');
if file_id < 0
    error('EU2607:OutputFailure', 'cannot create CSV output: %s', message);
end
cleanup = onCleanup(@() fclose(file_id)); %#ok<NASGU>
fprintf(file_id, ...
    'run,effective_seed,generations,logical_evaluations,final_fitness,final_lambda,solved,status\n');
for row = 1:numel(rows.run)
    fprintf(file_id, '%d,%d,%d,%d,%.17g,%.17g,%d,%s\n', ...
        rows.run(row), rows.effective_seed(row), rows.generations(row), ...
        rows.logical_evaluations(row), rows.final_fitness(row), ...
        rows.final_lambda(row), rows.solved(row), rows.status{row});
end
end

function tf = has_isstring()
tf = exist('isstring', 'builtin') ~= 0 || exist('isstring', 'file') ~= 0;
end

function tf = is_scalar_integer(value)
tf = isnumeric(value) && ~islogical(value) && isreal(value) ...
    && isscalar(value) && isfinite(double(value)) ...
    && double(value) == fix(double(value));
end

function tf = is_scalar_real(value)
tf = isnumeric(value) && ~islogical(value) && isreal(value) ...
    && isscalar(value) && isfinite(double(value));
end
