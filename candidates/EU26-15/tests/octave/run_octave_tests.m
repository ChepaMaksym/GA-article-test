function report = run_octave_tests()
%RUN_OCTAVE_TESTS Verify every frozen EU26-15 transition independently.

  script_dir = fileparts(mfilename('fullpath'));
  candidate_dir = fileparts(fileparts(script_dir));
  implementation_dir = fullfile(candidate_dir, 'environments', 'matlab');
  addpath(implementation_dir);
  contract_path = fullfile(candidate_dir, 'config', ...
    'verification_contract.json');
  fixture_path = fullfile(candidate_dir, 'fixtures', ...
    'fuzzy_transition_cases.json');
  contract = jsondecode(fileread(contract_path));
  fixture = jsondecode(fileread(fixture_path));
  tolerance = fixture.absolute_tolerance;
  checks = 0;

  assert_true(strcmp(contract.candidate_id, 'EU26-15'), ...
    'candidate identity drift');
  assert_true(strcmp(contract.candidate_status, 'CONDITIONAL_NONELIGIBLE'), ...
    'candidate status drift');
  assert_true(strcmp(contract.verification_scope, ...
    'FORMULA_AND_SOURCE_TRANSITION_VALIDATION_ONLY'), ...
    'verification scope drift');
  assert_true(~contract.pass_full, 'PASS_FULL must remain false');
  assert_true(strcmp(contract.source_quirks.mutation_antecedent, ...
    'intFV(ft_input)'), 'mutation antecedent quirk drift');
  assert_true(~contract.source_quirks.additional_mutop_normalization, ...
    'extra mutop normalization is forbidden');
  checks = checks + 6;

  endpoint_names = fieldnames(fixture.universe_endpoints);
  for index = 1:numel(endpoint_names)
    name = endpoint_names{index};
    expected = fixture.universe_endpoints.(name);
    actual = eu2615_transition('universe', name);
    assert_true(numel(actual) == expected.length, ...
      ['universe length drift: ', name]);
    assert_close(actual(1), expected.first, tolerance, ...
      ['universe first drift: ', name]);
    assert_close(actual(end), expected.last, tolerance, ...
      ['universe last drift: ', name]);
    checks = checks + 3;
  end
  fv_universe = eu2615_transition('universe', 'fv');
  assert_true(0.699 > fv_universe(end), ...
    'decimal 0.699 must be outside the sampled FV universe');
  checks = checks + 1;

  cases = object_items(fixture.transition_cases);
  for index = 1:numel(cases)
    item = cases{index};
    actual = eu2615_transition('transition', item.fv, item.ft, ...
      item.mlc, item.ssc);
    assert_transition(actual, item.expected, tolerance, item.id);
    checks = checks + 6;
  end

  population = fixture.population_case;
  population_result = eu2615_transition('population', population.fitness, ...
    population.previous_mean_fitness, population.chromosomes);
  statistic_names = {'fv', 'ft', 'mlc', 'ssc'};
  for index = 1:numel(statistic_names)
    name = statistic_names{index};
    assert_close(population_result.statistics.(name), ...
      population.expected_statistics.(name), tolerance, ...
      ['population statistic drift: ', name]);
    checks = checks + 1;
  end
  assert_close(population_result.statistics.mean_fitness, 0.6, tolerance, ...
    'population mean drift');
  assert_transition(population_result.transition, ...
    population.expected_transition, tolerance, population.id);
  checks = checks + 7;

  rank_cases = object_items(fixture.feature_rank_cases);
  for index = 1:numel(rank_cases)
    item = rank_cases{index};
    actual = eu2615_transition('feature_rank', item.usage, item.benefit);
    assert_close(actual, item.expected_delta, tolerance, ...
      ['feature-rank drift: ', item.id]);
    checks = checks + 1;
  end

  int_fv = eu2615_transition('memberships', 'fv', 0.015);
  int_ft = eu2615_transition('memberships', 'ft', 0.015);
  assert_close(int_fv.low, 0.5, tolerance, 'intFV low regression');
  assert_close(int_fv.med, 0.0, tolerance, 'intFV medium regression');
  assert_close(int_ft.low, 0.0, tolerance, 'intFT low control');
  assert_close(int_ft.med, 1.0, tolerance, 'intFT medium control');
  quirk = eu2615_transition('transition', 0.25, 0.015, 20.0, ...
    0.2222222222222222);
  assert_close(quirk.mutpb, 0.2, tolerance, ...
    'mutation must classify FT through intFV');
  assert_true(abs(quirk.mutpb - 0.15) > 0.04, ...
    'corrected intFT behavior was accidentally used');
  checks = checks + 6;

  at_threshold = eu2615_transition('transition', 0.05, 0.015, 20.0, 0.75);
  above_threshold = eu2615_transition('transition', ...
    0.699, 0.699, 200.0, 0.7500000001);
  assert_true(strcmp(at_threshold.branch, 'fuzzy'), ...
    'ssc == 0.75 must use fuzzy branch');
  assert_true(strcmp(above_threshold.branch, 'similarity_override'), ...
    'ssc > 0.75 must override before fuzzy evaluation');
  assert_close(sum(above_threshold.mutop), 1.0, tolerance, ...
    'override mutop sum drift');
  checks = checks + 3;

  expect_failure(@() eu2615_transition('transition', ...
    0.699, 0.05, 20.0, 0.75), '0.699 zero-area control');
  expect_failure(@() eu2615_transition('transition', ...
    0.05, 0.05, 200.0, 0.75), 'MLC 200 zero-area control');
  expect_failure(@() eu2615_transition('transition', ...
    NaN, 0.05, 20.0, 0.3), 'nonfinite control');
  expect_failure(@() eu2615_transition('population', ...
    [0.0, 0.0], 0.0, {[1], [2]}), 'zero maximum fitness');
  expect_failure(@() eu2615_transition('population', ...
    0.5, 0.4, {[1]}), 'one chromosome');
  expect_failure(@() eu2615_transition('population', ...
    [0.5, 0.4], 0.45, {[], []}), 'empty Jaccard union');
  expect_failure(@() eu2615_transition('population', ...
    [0.5, 0.4], 0.45, {[1, 1], [2]}), 'duplicate gene');
  checks = checks + 7;

  report = struct();
  report.schema_version = '1.0.0';
  report.candidate_id = 'EU26-15';
  report.candidate_status = 'CONDITIONAL_NONELIGIBLE';
  report.verification_scope = ...
    'FORMULA_AND_SOURCE_TRANSITION_VALIDATION_ONLY';
  report.status = 'PASS_OCTAVE_TRANSITION_FIXTURES';
  report.checks = checks;
  report.pass_full = false;
  report.empirical_replay = false;
  report.table_2_replay = false;
  fprintf('%s\n', jsonencode(report));
end


function values = object_items(value)
  if iscell(value)
    values = value(:)';
  elseif isstruct(value)
    values = num2cell(value(:)');
  else
    error('EU2615:FixtureShape', 'Expected JSON object array');
  end
end


function assert_transition(actual, expected, tolerance, label)
  assert_true(strcmp(actual.branch, expected.branch), ...
    ['branch drift: ', label]);
  assert_close(actual.cxpb, expected.cxpb, tolerance, ...
    ['cxpb drift: ', label]);
  assert_close(actual.mutpb, expected.mutpb, tolerance, ...
    ['mutpb drift: ', label]);
  actual_mutop = actual.mutop(:)';
  expected_mutop = expected.mutop(:)';
  assert_true(numel(actual_mutop) == 3 && numel(expected_mutop) == 3, ...
    ['mutop shape drift: ', label]);
  for index = 1:3
    assert_close(actual_mutop(index), expected_mutop(index), tolerance, ...
      ['mutop drift: ', label]);
  end
  assert_close(actual_mutop(3), 1.0 - ...
    (actual_mutop(1) + actual_mutop(2)), tolerance, ...
    ['mutop complement drift: ', label]);
end


function assert_close(actual, expected, tolerance, message)
  if ~isscalar(actual) || ~isfinite(actual) || ...
      abs(actual - expected) > tolerance
    error('EU2615:FixtureMismatch', '%s: actual %.17g expected %.17g', ...
      message, actual, expected);
  end
end


function assert_true(condition, message)
  if ~(islogical(condition) && isscalar(condition) && condition)
    error('EU2615:Assertion', '%s', message);
  end
end


function expect_failure(callback, label)
  failed = false;
  try
    callback();
  catch
    failed = true;
  end
  assert_true(failed, ['negative case unexpectedly passed: ', label]);
end
