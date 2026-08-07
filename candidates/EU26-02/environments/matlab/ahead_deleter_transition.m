function [next_state, event] = ahead_deleter_transition( ...
        state, selected_operators, child_penalties)
%AHEAD_DELETER_TRANSITION Apply one audited AHEAD/Deleter source turn.
%
% The two post-local-search child penalties update lifetime arithmetic
% means sequentially. Deletion is evaluated after both score updates and
% before TURN is incremented. At source turn 30 and every fifth turn after
% that, the surviving operator with the largest lifetime mean is removed.
% Equal means remove the lowest surviving zero-based operator identifier.

validate_state(state);
selected_operators = validate_selected_operators( ...
    selected_operators, state);
child_penalties = validate_child_penalties(child_penalties, state.nb_selected);

next_state = state;
event = struct();
event.source_turn = state.turn;
event.did_delete = false;
event.removed_operator = zeros(1, 0);

for selected_index = 1:state.nb_selected
    operator_id = selected_operators(selected_index);
    matlab_index = operator_id + 1;
    old_count = next_state.nb_times_used_total(matlab_index);
    old_mean = next_state.mean_score(matlab_index);
    new_count = old_count + 1;
    new_mean = ((old_mean * old_count) ...
        + child_penalties(selected_index)) / new_count;
    if ~isfinite(new_mean)
        error('EU2602:DeleterNumericalFailure', ...
            'A lifetime-mean update produced a non-finite value');
    end
    next_state.mean_score(matlab_index) = new_mean;
    next_state.nb_times_used_total(matlab_index) = new_count;
end

warmup_turns = 5 * state.nb_operators;
should_delete = state.turn >= warmup_turns ...
    && mod(state.turn, 5) == 0 ...
    && numel(state.possible_operators) > 1;
if should_delete
    survivor_indices = state.possible_operators + 1;
    survivor_means = next_state.mean_score(survivor_indices);
    worst_mean = max(survivor_means);
    % POSSIBLE_OPERATORS is strictly increasing, and FIND returns the first
    % maximum. This reproduces the ordered std::set plus strict-'>' C++ tie.
    worst_position = find(survivor_means == worst_mean, 1, 'first');
    removed_operator = state.possible_operators(worst_position);
    next_state.possible_operators(worst_position) = [];
    next_state.removed_operators = sort( ...
        [next_state.removed_operators, removed_operator]);
    event.did_delete = true;
    event.removed_operator = removed_operator;
end

next_state.turn = state.turn + 1;
validate_state(next_state);
end

function validate_state(state)
if ~isstruct(state) || ~isscalar(state)
    error('EU2602:BadDeleterState', 'State must be a scalar struct');
end
required = { ...
    'nb_operators', ...
    'nb_selected', ...
    'turn', ...
    'possible_operators', ...
    'removed_operators', ...
    'nb_times_used_total', ...
    'mean_score'};
for field_index = 1:numel(required)
    if ~isfield(state, required{field_index})
        error('EU2602:BadDeleterState', ...
            'Missing state field: %s', required{field_index});
    end
end

if ~is_scalar_integer(state.nb_operators) || state.nb_operators ~= 6
    error('EU2602:BadDeleterState', ...
        'The frozen EU26-02 configuration requires six operators');
end
if ~is_scalar_integer(state.nb_selected) || state.nb_selected ~= 2
    error('EU2602:BadDeleterState', ...
        'The frozen EU26-02 configuration requires two selections per turn');
end
if ~is_scalar_integer(state.turn) || state.turn < 0
    error('EU2602:BadDeleterState', ...
        'TURN must be a finite non-negative integer');
end

counts = require_row_vector( ...
    state.nb_times_used_total, state.nb_operators, 'nb_times_used_total', ...
    'EU2602:BadDeleterState');
if any(~isfinite(counts)) || any(counts < 0) || any(counts ~= round(counts))
    error('EU2602:BadDeleterState', ...
        'Lifetime counts must be finite non-negative integers');
end
means = require_row_vector( ...
    state.mean_score, state.nb_operators, 'mean_score', ...
    'EU2602:BadDeleterState');
if any(~isfinite(means)) || any(means < 0)
    error('EU2602:BadDeleterState', ...
        'Lifetime means must be finite and non-negative');
end
if any(means(counts == 0) ~= 0)
    error('EU2602:BadDeleterState', ...
        'An unused operator must retain its zero initial mean');
end

possible = require_operator_set( ...
    state.possible_operators, state.nb_operators, 'possible_operators', false);
removed = require_operator_set( ...
    state.removed_operators, state.nb_operators, 'removed_operators', true);
if ~isequal(sort([possible, removed]), 0:(state.nb_operators - 1))
    error('EU2602:BadDeleterState', ...
        'Possible and removed operators must partition all operator IDs');
end
end

function selected = validate_selected_operators(selected, state)
selected = require_row_vector( ...
    selected, state.nb_selected, 'selected_operators', ...
    'EU2602:BadDeleterInput');
if any(~isfinite(selected)) || any(selected ~= round(selected)) ...
        || any(selected < 0) || any(selected >= state.nb_operators)
    error('EU2602:BadDeleterInput', ...
        'Selected operators must be valid zero-based integer IDs');
end
if any(~ismember(selected, state.possible_operators))
    error('EU2602:BadDeleterInput', ...
        'A removed operator cannot be selected');
end
end

function penalties = validate_child_penalties(penalties, expected_count)
penalties = require_row_vector( ...
    penalties, expected_count, 'child_penalties', ...
    'EU2602:BadDeleterInput');
if any(~isfinite(penalties)) || any(penalties < 0) ...
        || any(penalties ~= round(penalties))
    error('EU2602:BadDeleterInput', ...
        'Child penalties must be finite non-negative integers');
end
end

function values = require_row_vector( ...
        values, expected_count, name, error_identifier)
if ~isnumeric(values) || ~isreal(values) || ~isvector(values) ...
        || size(values, 1) ~= 1 || numel(values) ~= expected_count
    error(error_identifier, ...
        '%s must contain exactly %d real numeric values', name, expected_count);
end
values = reshape(values, 1, []);
end

function values = require_operator_set(values, nb_operators, name, may_be_empty)
if may_be_empty && isempty(values)
    if ~isnumeric(values) || ~isreal(values) || size(values, 1) ~= 1
        error('EU2602:BadDeleterState', ...
            '%s must be a row-vector operator set', name);
    end
    return;
end
if ~isnumeric(values) || ~isreal(values) || ~isvector(values) ...
        || size(values, 1) ~= 1 || isempty(values)
    error('EU2602:BadDeleterState', '%s must be an operator vector', name);
end
values = reshape(values, 1, []);
if any(~isfinite(values)) || any(values ~= round(values)) ...
        || any(values < 0) || any(values >= nb_operators) ...
        || any(diff(values) <= 0)
    error('EU2602:BadDeleterState', ...
        '%s must contain unique increasing zero-based IDs', name);
end
end

function tf = is_scalar_integer(value)
tf = isnumeric(value) && isreal(value) && isscalar(value) ...
    && isfinite(value) && value == round(value);
end
