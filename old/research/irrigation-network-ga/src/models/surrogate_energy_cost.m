function cost = surrogate_energy_cost(branch_diameter_mm, frequency_Hz)
% Simplified pump-energy cost surrogate using article-style pump variables.
basic = article_basic_information();
sectoring = article_table1_rotation_sectoring();

electricityPrice_yuan_per_kWh = 0.8;
waterUtilizationCoefficient = 0.9;
frequency_Hz = frequency_Hz(:).';
branch_diameter_mm = branch_diameter_mm(:).';

if numel(frequency_Hz) ~= size(sectoring.branch_pipe_pairs, 1)
    error('Expected one frequency per irrigation sectoring.');
end

cost = 0;
for sector = 1:size(sectoring.branch_pipe_pairs, 1)
    pair = sectoring.branch_pipe_pairs(sector, :);
    pairDiameter = mean(branch_diameter_mm(pair));
    frequency = frequency_Hz(sector);

    flow_m3_h = 620 * (pairDiameter / 250)^0.65 * (frequency / 45);
    head_m = 12.5 * (250 / pairDiameter)^1.25 * (frequency / 45)^2;
    efficiency_pct = max(60, 81 - 0.10 * (frequency - 46)^2 - 0.0007 * (pairDiameter - 250)^2);
    period_h = 8.0 * (620 / flow_m3_h);

    hydraulicEnergy_kWh = flow_m3_h * head_m * period_h / ...
        (367.2 * (efficiency_pct / 100) * waterUtilizationCoefficient);
    cost = cost + basic.energy_consumption_correction_coefficient * ...
        electricityPrice_yuan_per_kWh * hydraulicEnergy_kWh;
end
end
