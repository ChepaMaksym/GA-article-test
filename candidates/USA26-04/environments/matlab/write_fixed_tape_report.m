function write_fixed_tape_report(output_path)
%WRITE_FIXED_TAPE_REPORT Emit a provenance-bound MATLAB/Octave H2 report.

if nargin ~= 1 || ~(ischar(output_path) || (isstring(output_path) && isscalar(output_path)))
    error('banditverify:InvalidOutput', 'One output path is required.');
end
implementation_dir = fileparts(mfilename('fullpath'));
candidate_root = fileparts(fileparts(implementation_dir));
repository_root = fileparts(fileparts(candidate_root));
fixture_path = fullfile(candidate_root, 'fixtures', 'fixed_controller_tape.json');
fixture = jsondecode(fileread(fixture_path));
payload = bandit_run_fixed_tape(fixture);

source_names = { ...
    'bandit_ambiguity_witnesses.m', ...
    'bandit_nesterov_update.m', ...
    'bandit_objective.m', ...
    'bandit_printed_eq2_literal.m', ...
    'bandit_reward.m', ...
    'bandit_run_fixed_tape.m', ...
    'bandit_tile_index.m', ...
    'write_fixed_tape_report.m'};
sources = repmat(struct('path', '', 'sha256', ''), 1, numel(source_names));
for index = 1:numel(source_names)
    sources(index).path = source_names{index};
    sources(index).sha256 = file_sha256( ...
        fullfile(implementation_dir, source_names{index}));
end

[git_status, git_output] = system(quoted_command( ...
    'git', repository_root, 'rev-parse HEAD'));
if git_status ~= 0
    error('banditverify:GitIdentity', 'Could not resolve current Git HEAD.');
end
git_sha = strtrim(git_output);
if isempty(regexp(git_sha, '^[0-9a-f]{40}$', 'once'))
    error('banditverify:GitIdentity', 'Git HEAD is not a full SHA-1.');
end

if exist('OCTAVE_VERSION', 'builtin') ~= 0
    engine_name = 'GNU Octave';
    engine_version = OCTAVE_VERSION;
else
    engine_name = 'MATLAB';
    engine_version = version;
end
canonical_payload = canonical_transition(payload);

report.schema_version = 'USA26-04-MATLAB-H2-REPORT-v1';
report.protocol_id = 'USA26-04-FORMULA-PORTABILITY-v1';
report.git_sha = git_sha;
report.implementation = 'matlab_octave_clean_room';
report.engine.name = engine_name;
report.engine.version = engine_version;
report.matlab_sources = sources;
report.fixture_path = 'fixtures/fixed_controller_tape.json';
report.fixture_sha256 = file_sha256(fixture_path);
report.payload = payload;
report.canonical_payload = canonical_payload;
report.canonical_payload_sha256 = text_sha256(canonical_payload);

encoded = jsonencode(report);
handle = fopen(char(output_path), 'w');
if handle < 0
    error('banditverify:OutputOpen', 'Could not open output path.');
end
cleanup = onCleanup(@() fclose(handle)); %#ok<NASGU>
fprintf(handle, '%s\n', encoded);
fprintf('Wrote provenance-bound synthetic fixed-tape report: %s\n', char(output_path));
end

function command = quoted_command(program, repository_root, arguments)
assert_safe_shell_path(repository_root);
command = sprintf('%s -C "%s" %s', program, repository_root, arguments);
end

function digest = file_sha256(path)
assert_safe_shell_path(path);
[status, output] = system(sprintf('sha256sum "%s"', path));
if status ~= 0
    error('banditverify:Sha256', 'sha256sum failed for %s.', path);
end
tokens = regexp(strtrim(output), '^([0-9a-f]{64})\s', 'tokens', 'once');
if isempty(tokens)
    error('banditverify:Sha256', 'Could not parse sha256sum output.');
end
digest = tokens{1};
end

function assert_safe_shell_path(path)
if isempty(regexp(char(path), '^[A-Za-z0-9_./-]+$', 'once'))
    error('banditverify:UnsafePath', ...
        'Shell-bound paths are restricted to a conservative safe alphabet.');
end
end

function digest = text_sha256(value)
temporary_path = tempname;
handle = fopen(temporary_path, 'wb');
if handle < 0
    error('banditverify:TemporaryFile', 'Could not open digest temporary file.');
end
cleanup_handle = onCleanup(@() fclose(handle)); %#ok<NASGU>
fwrite(handle, value, 'char');
clear cleanup_handle
cleanup_file = onCleanup(@() delete_if_present(temporary_path)); %#ok<NASGU>
digest = file_sha256(temporary_path);
end

function delete_if_present(path)
if exist(path, 'file') ~= 0
    delete(path);
end
end

function text = canonical_transition(payload)
lines = { ...
    'USA26-04-MATLAB-H2-PAYLOAD-v1', ...
    ['verification_scope=' payload.verification_scope], ...
    ['paper_level_status=' payload.paper_level_status], ...
    ['published_result_status=' payload.published_result_status], ...
    ['state_provenance=' payload.state_provenance], ...
    ['base_weights=' number_list(payload.base_weights)], ...
    ['branch=' payload.branch], ...
    ['argmax_tile=' number_text(payload.argmax_tile)], ...
    ['selected_tile=' number_text(payload.selected_tile)], ...
    ['log_rate=' number_text(payload.log_rate)], ...
    ['rate=' number_text(payload.rate)], ...
    ['immediate_reward=' number_text(payload.immediate_reward)]};
for position = 1:numel(payload.updates)
    update = payload.updates(position);
    index = position - 1;
    prefix = sprintf('updates[%d]', index);
    lines{end + 1} = [prefix '.coding=' number_text(update.coding)]; %#ok<AGROW>
    lines{end + 1} = [prefix '.paper_index=' number_text(update.paper_index)]; %#ok<AGROW>
    lines{end + 1} = [prefix '.history=' number_list(update.history)]; %#ok<AGROW>
    lines{end + 1} = [prefix '.max_reward=' number_text(update.max_reward)]; %#ok<AGROW>
    lines{end + 1} = [prefix '.gradient=' number_text(update.gradient)]; %#ok<AGROW>
    lines{end + 1} = [prefix '.momentum=' number_text(update.momentum)]; %#ok<AGROW>
    lines{end + 1} = [prefix '.value=' number_text(update.value)]; %#ok<AGROW>
end
text = [strjoin(lines, sprintf('\n')) sprintf('\n')];
end

function text = number_text(value)
if ~isnumeric(value) || ~isscalar(value) || ~isfinite(value)
    error('banditverify:CanonicalNumber', 'Canonical number must be finite scalar.');
end
text = sprintf('%.17g', double(value));
end

function text = number_list(values)
if ~isnumeric(values) || any(~isfinite(values(:)))
    error('banditverify:CanonicalNumber', 'Canonical list must be finite numeric.');
end
parts = cell(1, numel(values));
for index = 1:numel(values)
    parts{index} = number_text(values(index));
end
text = strjoin(parts, ',');
end
