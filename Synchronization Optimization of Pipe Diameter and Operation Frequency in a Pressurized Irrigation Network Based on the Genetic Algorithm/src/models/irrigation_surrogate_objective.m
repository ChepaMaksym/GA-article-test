function [objective, details] = irrigation_surrogate_objective(x)
% Surrogate objective: annualized network cost + energy cost + soft penalties.
prices = article_table3_pipe_prices();
diameterOptions = prices.outside_diameter_mm;

diameterIndex = round(x(1:10));
diameterIndex = min(max(diameterIndex, 1), numel(diameterOptions));
branchDiameter = diameterOptions(diameterIndex);

frequency = round(x(11:15));
frequency = min(max(frequency, 41), 50);

networkCost = annualized_network_cost(branchDiameter);
energyCost = surrogate_energy_cost(branchDiameter, frequency);
penalty = irrigation_surrogate_penalty(branchDiameter, frequency);
objective = networkCost + energyCost + penalty;

if nargout > 1
    details = struct();
    details.branch_diameter_mm = branchDiameter;
    details.frequency_Hz = frequency;
    details.network_cost = networkCost;
    details.energy_cost = energyCost;
    details.penalty = penalty;
    details.objective = objective;
end
end

function penalty = irrigation_surrogate_penalty(branchDiameter, frequency)
basic = article_basic_information();
penalty = 0;

% Article-style pressure/efficiency feasibility is unavailable without Figure 5.
% These soft terms keep the sandbox in plausible engineering ranges.
if mean(branchDiameter) < 180
    penalty = penalty + basic.lambda3 * (180 - mean(branchDiameter));
end

if any(frequency < 41 | frequency > 50)
    penalty = penalty + basic.lambda3 * sum(abs(frequency(frequency < 41 | frequency > 50) - 45));
end

% Encourage smoother sector frequency schedules.
penalty = penalty + basic.lambda1 * sum(abs(diff(frequency)) > 7);
end
