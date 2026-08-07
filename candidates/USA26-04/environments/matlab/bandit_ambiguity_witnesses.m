function result = bandit_ambiguity_witnesses()
%BANDIT_AMBIGUITY_WITNESSES Demonstrate conflicts without selecting semantics.

left = -100;
right = 100;
resolution = 0.03;
count = floor((right - left) / resolution);
last_clamped = count - 1;
last_lower = left + last_clamped * resolution;
last_upper = last_lower + resolution;
next_lower = left + count * resolution;
next_upper = next_lower + resolution;

result.verification_scope = 'FORMULA_AND_AMBIGUITY_VALIDATION_ONLY';
result.paper_level_status = 'BLOCKED_G5_G9';
result.published_result_status = 'INCONCLUSIVE_PUBLISHED_RESULT';
result.boundary.status = 'AMBIGUITY_CONFIRMED';
result.boundary.resolution_chosen = false;
result.boundary.floor_tile_count = count;
result.boundary.last_clamped_tile = last_clamped;
result.boundary.last_clamped_interval = [last_lower, last_upper];
result.boundary.next_tile = count;
result.boundary.next_interval = [next_lower, next_upper];
result.boundary.declared_right = right;
result.boundary.uncovered_width_if_clamped = right - last_upper;
result.boundary.overshoot_width_if_next_tile = next_upper - right;
result.tie.status = 'AMBIGUITY_CONFIRMED';
result.tie.resolution_chosen = false;
result.tie.maximizer_tiles = 0:3;
result.tie.selected_tile = [];
result.standard_deviation.status = 'AMBIGUITY_CONFIRMED';
result.standard_deviation.resolution_chosen = false;
result.standard_deviation.actual_sd_log_two_to_uniform = log(2) / sqrt(3);
result.standard_deviation.printed_symbolic_value = sqrt(2 * log(2) / 12);
result.standard_deviation.stated_numeric_value = 0.223;
result.standard_deviation.all_distinct_at_1e_3 = true;
end
