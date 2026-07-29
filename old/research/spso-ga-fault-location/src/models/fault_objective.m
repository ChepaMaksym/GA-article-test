function [objective, decodedSection] = fault_objective(position, observation)
[~, decodedSection] = max(position);
predicted = fault_signature(observation.network, decodedSection, observation.sensor_nodes);
mismatch = abs(predicted - observation.observed_signature);
objective = sum(mismatch) + 0.02 * abs(decodedSection - soft_section_estimate(position));
end

function section = soft_section_estimate(position)
weights = max(position(:), 0);
if sum(weights) <= 0
    section = 1;
else
    section = sum((1:numel(position))' .* weights) ./ sum(weights);
end
end
