function state = ahead_deleter_initial_state()
%AHEAD_DELETER_INITIAL_STATE Frozen AHEAD/Deleter state for EU26-02.
%
% Operator identifiers are zero-based to match the audited C++ source.
% The publication configuration contains six crossover/local-search pairs
% and selects two child actions per source turn.

state = struct();
state.nb_operators = 6;
state.nb_selected = 2;
state.turn = 0;
state.possible_operators = 0:5;
state.removed_operators = zeros(1, 0);
state.nb_times_used_total = zeros(1, 6);
state.mean_score = zeros(1, 6);
end
