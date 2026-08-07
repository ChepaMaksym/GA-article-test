function result = bandit_run_fixed_tape(fixture)
%BANDIT_RUN_FIXED_TAPE Run only the explicitly synthetic interior transition.

provenance = 'synthetic_fixture_not_article_state';
if ~isstruct(fixture) || ~isfield(fixture, 'description') ...
        || isempty(strfind(fixture.description, 'not article state')) %#ok<STREMP>
    error('banditverify:MissingProvenance', ...
        'Fixture must say that its state is not article state.');
end
if ~strcmp(fixture.reward_semantics, 'P1')
    error('banditverify:InvalidFixtureSemantics', ...
        'The frozen fixture requires primary semantics P1.');
end

search = fixture.search;
tape = fixture.tape;
codings = fixture.codings;
left = search.left;
right = search.right;
resolution = search.resolution;
raw_count = (right - left) / resolution;
base_tile_count = round(raw_count);
if left >= right || resolution <= 0 || abs(raw_count - base_tile_count) > 1e-12
    error('banditverify:InvalidFixtureRange', ...
        'Synthetic fixture range must have exact positive base tiles.');
end
if search.history_length < 1 || search.history_length ~= floor(search.history_length)
    error('banditverify:InvalidHistoryLength', ...
        'History length must be a positive integer.');
end

base_weights = zeros(1, base_tile_count);
for base_position = 1:base_tile_count
    base_index = base_position - 1;
    point = left + base_index * resolution;
    associated = zeros(1, numel(codings));
    for coding_index = 1:numel(codings)
        coding = codings(coding_index);
        paper_index = bandit_tile_index( ...
            point, left, coding.offset, coding.width);
        associated(coding_index) = state_value( ...
            coding.values_by_paper_index, paper_index);
    end
    base_weights(base_position) = mean(associated);
end

if tape.epsilon_uniform < search.epsilon
    branch = 'explore';
    selected_before_noise = tape.exploration_tile;
    argmax_tile = [];
else
    branch = 'exploit';
    maximum = max(base_weights);
    maximizers = find(base_weights == maximum) - 1;
    if numel(maximizers) ~= 1
        error('banditverify:AmbiguousTie', ...
            'Fixed-tape transition requires a unique maximum.');
    end
    argmax_tile = maximizers(1);
    selected_before_noise = argmax_tile;
end
if tape.noise_floor ~= floor(tape.noise_floor)
    error('banditverify:InvalidTape', 'noise_floor must already be an integer.');
end
selected_tile = min(max(selected_before_noise + tape.noise_floor, 0), ...
    base_tile_count - 1);
if tape.within_tile_uniform < 0 || tape.within_tile_uniform >= 1
    error('banditverify:InvalidTape', ...
        'within_tile_uniform must be in [0,1).');
end
log_rate = left + resolution * (selected_tile + tape.within_tile_uniform);
rate = exp(log_rate);
immediate_reward = bandit_reward( ...
    'P1', fixture.parent_error, fixture.child_error);

updates = repmat(struct( ...
    'coding', 0, ...
    'paper_index', 0, ...
    'history', [], ...
    'max_reward', 0, ...
    'gradient', 0, ...
    'momentum', 0, ...
    'value', 0), 1, numel(codings));
for coding_position = 1:numel(codings)
    coding = codings(coding_position);
    paper_index = bandit_tile_index( ...
        log_rate, left, coding.offset, coding.width);
    history = state_history(coding.histories_by_paper_index, paper_index);
    history = [history(:).', immediate_reward]; %#ok<AGROW>
    if numel(history) > search.history_length
        history = history(end-search.history_length+1:end);
    end
    max_reward = max(history);
    update = bandit_nesterov_update( ...
        state_value(coding.values_by_paper_index, paper_index), ...
        state_value(coding.momenta_by_paper_index, paper_index), ...
        max_reward, coding.learning_rate, coding.momentum_factor);
    updates(coding_position).coding = coding_position - 1;
    updates(coding_position).paper_index = paper_index;
    updates(coding_position).history = history;
    updates(coding_position).max_reward = max_reward;
    updates(coding_position).gradient = update.gradient;
    updates(coding_position).momentum = update.momentum;
    updates(coding_position).value = update.value;
end

result.verification_scope = 'FORMULA_AND_AMBIGUITY_VALIDATION_ONLY';
result.paper_level_status = 'BLOCKED_G5_G9';
result.published_result_status = 'INCONCLUSIVE_PUBLISHED_RESULT';
result.state_provenance = provenance;
result.base_weights = base_weights;
result.branch = branch;
result.argmax_tile = argmax_tile;
result.selected_tile = selected_tile;
result.log_rate = log_rate;
result.rate = rate;
result.immediate_reward = immediate_reward;
result.updates = updates;
end

function value = state_value(sequence, paper_index)
position = paper_index + 1;
if iscell(sequence)
    if position > numel(sequence)
        error('banditverify:MissingSyntheticState', ...
            'Paper index has no supplied state.');
    end
    value = sequence{position};
else
    if position > numel(sequence)
        error('banditverify:MissingSyntheticState', ...
            'Paper index has no supplied state.');
    end
    value = sequence(position);
end
if isempty(value) || ~isnumeric(value) || ~isscalar(value) || ~isfinite(value)
    error('banditverify:MissingSyntheticState', ...
        'Paper index points to missing synthetic state.');
end
value = double(value);
end

function history = state_history(sequence, paper_index)
position = paper_index + 1;
if iscell(sequence)
    history = sequence{position};
else
    history = sequence(position, :);
    history = history(isfinite(history));
end
if isempty(history)
    history = [];
elseif ~isnumeric(history) || any(~isfinite(history(:)))
    error('banditverify:InvalidHistory', ...
        'Synthetic history must be a finite numeric vector.');
end
history = double(history);
end
