function run_octave_tests(contract_path, fixture_path, output_path)
  % Independent GNU Octave controls for the preregistered EU26-13 fixtures.
  script_dir = fileparts(mfilename('fullpath'));
  candidate_dir = fileparts(fileparts(script_dir));
  if nargin < 1 || isempty(contract_path)
    contract_path = fullfile(candidate_dir, 'config', 'verification_contract.json');
  endif
  if nargin < 2 || isempty(fixture_path)
    fixture_path = fullfile(candidate_dir, 'fixtures', 'frozen_endpoint.json');
  endif
  if nargin < 3 || isempty(output_path)
    output_path = fullfile(candidate_dir, 'results', 'octave-controls.json');
  endif

  contract = jsondecode(fileread(contract_path));
  fixture = jsondecode(fileread(fixture_path));
  checks = struct();

  checks.boundary = strcmp(contract.status, 'TARGETED_ARTIFACT_REPLAY_ONLY') ...
    && strcmp(contract.paper_mapping, 'PAPER_CONTEXT_ONLY') ...
    && strcmp(contract.source_native_status, 'BLOCKED_UNPINNED_TOOLCHAIN_DEPS') ...
    && contract.verification_execution.source_native_execution_forbidden_under_v1;

  endpoint = contract.endpoint;
  checks.endpoint_schema = strcmp(fixture.algorithm_name, endpoint.algorithm_name) ...
    && strcmp(fixture.json_version, endpoint.json_version) ...
    && strcmp(fixture.suite, endpoint.suite) ...
    && fixture.dimension == 20 ...
    && fixture.runs == 500 ...
    && isequal(fixture.scenario_dimensions(:)', endpoint.scenario_dimensions(:)');
  checks.endpoint_value = strcmp(fixture.best_y_decimal, endpoint.best_y_decimal) ...
    && fixture.evals == endpoint.evals ...
    && fixture.best_evals == endpoint.best_evals ...
    && fixture.best_x_length == endpoint.best_x_length ...
    && fixture.instance == endpoint.instance ...
    && fixture.run_index == endpoint.run_index ...
    && fixture.seed == endpoint.seed;

  seed_cfg = contract.control_fixtures.seed_schedule;
  seed_rows = seed_cfg.instances * seed_cfg.runs_per_instance;
  schedule = zeros(seed_rows, 3);
  cursor = 1;
  for instance = 1:seed_cfg.instances
    for run = 0:(seed_cfg.runs_per_instance - 1)
      schedule(cursor, :) = [instance, run, seed_cfg.seed_multiplier * run];
      cursor += 1;
    endfor
  endfor
  checks.seed_schedule = rows(schedule) == seed_cfg.expected_rows ...
    && isequal(schedule(1, :), seed_cfg.expected_first(:)') ...
    && isequal(schedule(seed_cfg.runs_per_instance + 1, :), seed_cfg.expected_instance2_first(:)') ...
    && isequal(schedule(end, :), seed_cfg.expected_last(:)');

  bipop = contract.control_fixtures.bipop;
  lambda_init = bipop.lambda_init;
  mu_factor = bipop.mu_init / lambda_init;
  total_budget = bipop.budget;
  first_cfg = bipop.first_restart;
  used_budget = first_cfg.evaluations;
  remaining_budget = total_budget - used_budget;
  budget_small = floor(remaining_budget / 2);
  budget_large = remaining_budget - budget_small;
  lambda_large = lambda_init * 2;
  first_floor = floor(lambda_init * (0.5 / lambda_large / lambda_init)^(first_cfg.uniform_population^2));
  first_small = first_floor + mod(first_floor, 2);
  first_is_large = budget_large >= budget_small && budget_large > 0;
  if first_is_large
    first_lambda = lambda_large;
    first_sigma = first_cfg.expected_sigma;
  else
    first_lambda = max(2, first_small);
    first_sigma = first_cfg.expected_sigma * 10^0;
  endif
  first_mu = max(1, fix(first_lambda * mu_factor));
  checks.bipop_first = budget_small == first_cfg.expected_budget_small ...
    && budget_large == first_cfg.expected_budget_large ...
    && lambda_large == first_cfg.expected_lambda_large ...
    && first_floor == first_cfg.expected_lambda_small_proposal ...
    && first_lambda == first_cfg.expected_lambda ...
    && first_mu == first_cfg.expected_mu ...
    && close_enough(first_sigma, first_cfg.expected_sigma, 2e-14);

  second_cfg = bipop.second_restart;
  last_used_budget = second_cfg.evaluations - used_budget;
  used_budget = second_cfg.evaluations;
  previous_large = budget_large >= budget_small && budget_large > 0;
  if previous_large
    budget_large -= last_used_budget;
    lambda_large *= 2;
  else
    budget_small -= last_used_budget;
  endif
  second_floor = floor(lambda_init * (0.5 / lambda_large / lambda_init)^(second_cfg.uniform_population^2));
  lambda_small = second_floor + mod(second_floor, 2);
  second_is_large = budget_large >= budget_small && budget_large > 0;
  if second_is_large
    second_lambda = lambda_large;
    second_sigma = first_cfg.expected_sigma;
  else
    second_lambda = max(2, lambda_small);
    second_sigma = first_cfg.expected_sigma * 10^(-2 * second_cfg.uniform_sigma);
  endif
  second_mu = max(1, fix(second_lambda * mu_factor));
  checks.bipop_second = budget_small == second_cfg.expected_budget_small ...
    && budget_large == second_cfg.expected_budget_large ...
    && lambda_large == second_cfg.expected_lambda_large ...
    && lambda_small == second_cfg.expected_lambda_small ...
    && second_lambda == second_cfg.expected_lambda ...
    && second_mu == second_cfg.expected_mu ...
    && close_enough(second_sigma, second_cfg.expected_sigma, 2e-14);

  radius_cfg = contract.control_fixtures.repelling_radius;
  dimension = radius_cfg.dimension;
  volume = str2double(radius_cfg.volume);
  volume_per_n = volume / (radius_cfg.sigma0 * radius_cfg.coverage * radius_cfg.finalized_restarts);
  gamma_factor = gamma(dimension / 2 + 1)^(1 / dimension) / sqrt(pi);
  radius = (volume_per_n * radius_cfg.n_rep)^(1 / dimension) * gamma_factor;
  shrinkage = 0.99^(1 / dimension);
  effective_radius = shrinkage^radius_cfg.attempts * radius;
  checks.repelling = close_enough(gamma_factor, radius_cfg.expected_gamma_factor, 2e-14) ...
    && close_enough(radius, radius_cfg.expected_radius, 2e-14) ...
    && close_enough(shrinkage, radius_cfg.expected_shrinkage, 2e-14) ...
    && close_enough(effective_radius, radius_cfg.expected_effective_radius, 2e-14);

  csa_cfg = contract.control_fixtures.csa;
  csa_sigma = csa_cfg.sigma * exp((csa_cfg.cs / csa_cfg.damps) * ((csa_cfg.ps_norm / csa_cfg.chi_n) - 1));
  checks.csa = close_enough(csa_sigma, csa_cfg.expected_sigma, 2e-14);

  hill_cfg = contract.control_fixtures.hill_valley;
  fractions = (1:hill_cfg.n_evals) / (hill_cfg.n_evals + 1);
  [same_equal, equal_evals] = hill_valley_control(1.0, 2.0, [2.0, 1.5, 2.0]);
  [same_barrier, barrier_evals] = hill_valley_control(1.0, 2.0, [1.5, 2.0000000001, 1.0]);
  checks.hill_valley = isequal(fractions, hill_cfg.expected_interpolation_fractions(:)') ...
    && same_equal && equal_evals == 3 ...
    && !same_barrier && barrier_evals == 2;

  values = struct();
  values.seed_rows = rows(schedule);
  values.seed_last = schedule(end, :);
  values.first_lambda = first_lambda;
  values.second_lambda = second_lambda;
  values.second_sigma = second_sigma;
  values.repelling_radius = radius;
  values.repelling_shrinkage = shrinkage;
  values.csa_sigma = csa_sigma;
  values.hill_fractions = fractions;
  values.endpoint_best_y_decimal = fixture.best_y_decimal;

  check_values = struct2cell(checks);
  if !all(cellfun(@(value) islogical(value) && isscalar(value) && value, check_values))
    error('EU26-13:ControlFailure', 'At least one independent Octave control failed');
  endif
  if exist(output_path, 'file')
    error('EU26-13:WriteOnce', 'Refusing to overwrite %s', output_path);
  endif
  output_dir = fileparts(output_path);
  if !isempty(output_dir) && !exist(output_dir, 'dir')
    mkdir(output_dir);
  endif
  report = struct();
  report.schema_version = '1.0.0';
  report.candidate_id = 'EU26-13';
  report.status = 'PASS_CROSS_LANGUAGE_CONTROLS';
  report.paper_mapping = 'PAPER_CONTEXT_ONLY';
  report.source_native_status = 'BLOCKED_UNPINNED_TOOLCHAIN_DEPS';
  report.contract_sha256 = hash('sha256', fileread(contract_path));
  report.fixture_sha256 = hash('sha256', fileread(fixture_path));
  report.octave_script_sha256 = hash('sha256', fileread([mfilename('fullpath'), '.m']));
  report.checks = checks;
  report.values = values;
  handle = fopen(output_path, 'w');
  if handle < 0
    error('EU26-13:Output', 'Could not create %s', output_path);
  endif
  unwind_protect
    fprintf(handle, '%s\n', jsonencode(report));
  unwind_protect_cleanup
    fclose(handle);
  end_unwind_protect
  fprintf('PASS_CROSS_LANGUAGE_CONTROLS: %s\n', output_path);
endfunction


function value = close_enough(actual, expected, tolerance)
  value = isfinite(actual) && abs(actual - expected) <= tolerance * max([1, abs(actual), abs(expected)]);
endfunction


function [same_basin, evaluations] = hill_valley_control(endpoint_a, endpoint_b, values)
  maximum = max(endpoint_a, endpoint_b);
  evaluations = 0;
  same_basin = true;
  for value = values
    evaluations += 1;
    if maximum < value
      same_basin = false;
      return;
    endif
  endfor
endfunction
