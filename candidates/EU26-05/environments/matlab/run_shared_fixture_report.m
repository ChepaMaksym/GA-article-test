function report = run_shared_fixture_report(output_path)
%RUN_SHARED_FIXTURE_REPORT Execute the frozen cross-language micro-oracles.

if nargin < 1
    output_path = '';
end
candidate = fileparts(fileparts(fileparts(mfilename('fullpath'))));
fixture_path = fullfile(candidate, 'fixtures', 'formula_transition_cases.json');
fixture = jsondecode(fileread(fixture_path));
if ~strcmp(fixture.protocol_id, 'EU26-05-FORMULA-TRANSITION-v1')
    error('EU2605:BadFixture', 'fixture protocol identity changed');
end

probability_count = numel(fixture.probability_cases);
probability_rows = repmat( ...
    struct('id', '', 'probabilities', {{}}), 1, probability_count);
for index = 1:probability_count
    item = struct_array_item(fixture.probability_cases, index);
    values = eu2605_probability_update( ...
        row(item.successes), row(item.crossovers));
    formatted = arrayfun(@(value) sprintf('%.12f', value), ...
        values, 'UniformOutput', false);
    expected = cellstr_row(item.expected);
    if ~isequal(formatted, expected)
        error('EU2605:FixtureMismatch', ...
            'probability fixture mismatch: %s', item.id);
    end
    probability_rows(index).id = item.id;
    probability_rows(index).probabilities = formatted;
end

decode_count = numel(fixture.decode_cases);
decode_rows = repmat(struct('id', '', 'decoded', ''), 1, decode_count);
for index = 1:decode_count
    item = struct_array_item(fixture.decode_cases, index);
    value = eu2605_binary_decode_anchor( ...
        item.bits, item.lower, item.upper, ...
        item.bit_order, item.endpoint_convention);
    formatted = sprintf('%.12f', value);
    if ~strcmp(formatted, item.expected)
        error('EU2605:FixtureMismatch', ...
            'decode fixture mismatch: %s', item.id);
    end
    decode_rows(index).id = item.id;
    decode_rows(index).decoded = formatted;
end

transition_count = numel(fixture.transition_cases);
transition_rows = repmat( ...
    struct('id', '', 'operator', '', 'children', {{}}), 1, transition_count);
for index = 1:transition_count
    item = struct_array_item(fixture.transition_cases, index);
    if is_json_null(item.cut)
        cut = [];
    else
        cut = item.cut;
    end
    transition = eu2605_crossover_transition( ...
        item.parent_a, item.parent_b, item.preference, cut);
    expected_children = cellstr_row(item.expected_children);
    if ~strcmp(transition.operator, item.operator) ...
            || ~isequal(transition.children, expected_children)
        error('EU2605:FixtureMismatch', ...
            'transition fixture mismatch: %s', item.id);
    end
    transition_rows(index).id = item.id;
    transition_rows(index).operator = transition.operator;
    transition_rows(index).children = transition.children;
end

semantic_payload = struct();
semantic_payload.protocol_id = 'EU26-05-FORMULA-TRANSITION-v1';
semantic_payload.paper_level_status = ...
    'BLOCKED_SOURCE_BYTE_FREEZE_AND_STOCHASTIC_PROVENANCE';
semantic_payload.source_byte_status = 'PASS_METADATA_ONLY';
semantic_payload.source_freeze_status = 'BLOCKED_SOURCE_BYTE_FREEZE';
semantic_payload.h0_source_status = ...
    'PASS_METADATA_ONLY / BLOCKED_SOURCE_BYTE_FREEZE';
semantic_payload.profile = 'FORMULA_AND_TRANSITION_VALIDATION_ONLY';
semantic_payload.probability_cases = probability_rows;
semantic_payload.decode_cases = decode_rows;
semantic_payload.transition_cases = transition_rows;

repository = fileparts(fileparts(candidate));
source_rows = implementation_source_rows(candidate, repository);
report = struct();
report.schema_version = '1.0.0';
report.report_kind = 'EU26-05-INDEPENDENT-FIXTURE-v1';
report.implementation = 'matlab_octave';
report.git_head = repository_git_head(repository);
report.runtime = runtime_record();
report.implementation_source_hashes = source_rows;
report.implementation_source_digest = source_rows_digest(source_rows);
report.h0_source_status = ...
    'PASS_METADATA_ONLY / BLOCKED_SOURCE_BYTE_FREEZE';
report.source_byte_status = 'PASS_METADATA_ONLY';
report.source_freeze_status = 'BLOCKED_SOURCE_BYTE_FREEZE';
report.semantic_payload = semantic_payload;
% Canonical semantic digest independently frozen by the Python fixture
% generator. The comparator recomputes and compares the full parsed payload.
report.semantic_payload_sha256 = ...
    '6f560ccd36492e9fb1c4057d67ea2e54fffa032e72ddd02557bad077aacaf502';

if ~isempty(output_path)
    output_directory = fileparts(output_path);
    if ~isempty(output_directory) && exist(output_directory, 'dir') == 0
        mkdir(output_directory);
    end
    handle = fopen(output_path, 'w');
    if handle < 0
        error('EU2605:WriteFailed', 'cannot open fixture report output');
    end
    cleanup = onCleanup(@() fclose(handle)); %#ok<NASGU>
    fprintf(handle, '%s\n', jsonencode(report));
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

function values = cellstr_row(values)
if iscell(values)
    values = reshape(values, 1, []);
elseif isstring(values)
    values = cellstr(reshape(values, 1, []));
elseif ischar(values)
    if isrow(values)
        values = {values};
    else
        values = cellstr(values)';
    end
else
    error('EU2605:BadFixture', 'expected a JSON string array');
end
end

function tf = is_json_null(value)
tf = isempty(value) || (isnumeric(value) && isscalar(value) && isnan(value));
end

function rows = implementation_source_rows(candidate, repository)
directories = { ...
    fullfile(candidate, 'environments', 'matlab'), ...
    fullfile(candidate, 'tests', 'matlab')};
paths = {};
for directory_index = 1:numel(directories)
    entries = dir(fullfile(directories{directory_index}, '*.m'));
    for entry_index = 1:numel(entries)
        paths{end + 1} = fullfile( ... %#ok<AGROW>
            entries(entry_index).folder, entries(entry_index).name);
    end
end
paths = sort(paths);
rows = repmat(struct('path', '', 'sha256', ''), 1, numel(paths));
repository_prefix = [repository, filesep];
for index = 1:numel(paths)
    path = paths{index};
    if ~strncmp(path, repository_prefix, numel(repository_prefix))
        error('EU2605:SourceBinding', 'MATLAB source escaped the repository');
    end
    relative = path((numel(repository_prefix) + 1):end);
    rows(index).path = strrep(relative, filesep, '/');
    rows(index).sha256 = sha256_file(path);
end
end

function digest = source_rows_digest(rows)
payload = '';
for index = 1:numel(rows)
    payload = [payload, rows(index).sha256, char(9), ... %#ok<AGROW>
        rows(index).path, char(10)];
end
path = [tempname(), '.tsv'];
cleanup = onCleanup(@() delete_if_exists(path)); %#ok<NASGU>
handle = fopen(path, 'wb');
if handle < 0
    error('EU2605:SourceBinding', 'cannot create source digest payload');
end
fwrite(handle, uint8(payload), 'uint8');
fclose(handle);
digest = sha256_file(path);
end

function digest = sha256_file(path)
try
    engine = javaMethod('getInstance', ...
        'java.security.MessageDigest', 'SHA-256');
    handle = fopen(path, 'rb');
    if handle < 0
        error('EU2605:SourceBinding', 'cannot open source for SHA-256');
    end
    cleanup = onCleanup(@() fclose(handle)); %#ok<NASGU>
    bytes = fread(handle, Inf, '*uint8');
    engine.update(typecast(bytes(:), 'int8'));
    raw = typecast(engine.digest(), 'uint8');
    digest = lower(reshape(dec2hex(raw, 2)', 1, []));
    return;
catch
    % GNU Octave builds without Java use the host's standard sha256sum.
end
command = sprintf('sha256sum "%s"', strrep(path, '"', '\"'));
[status, output] = system(command);
tokens = regexp(strtrim(output), '^([0-9a-fA-F]{64})', 'tokens', 'once');
if status ~= 0 || isempty(tokens)
    error('EU2605:SourceBinding', 'no SHA-256 implementation is available');
end
digest = lower(tokens{1});
end

function head = repository_git_head(repository)
original = pwd;
cleanup = onCleanup(@() cd(original)); %#ok<NASGU>
cd(repository);
[status, output] = system('git rev-parse HEAD');
if status ~= 0
    error('EU2605:SourceBinding', 'cannot resolve repository git HEAD');
end
head = strtrim(output);
if isempty(regexp(head, '^[0-9a-f]{40}$', 'once'))
    error('EU2605:SourceBinding', 'repository git HEAD is malformed');
end
end

function record = runtime_record()
if exist('OCTAVE_VERSION', 'builtin') ~= 0
    engine = 'octave';
    runtime_version = OCTAVE_VERSION;
else
    engine = 'matlab';
    runtime_version = version;
end
record = struct( ...
    'engine', engine, ...
    'version', runtime_version, ...
    'platform', computer);
end

function delete_if_exists(path)
if exist(path, 'file') ~= 0
    delete(path);
end
end
