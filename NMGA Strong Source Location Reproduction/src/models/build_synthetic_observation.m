function observation = build_synthetic_observation(caseData)
sensors = synthetic_sensor_grid(caseData.layout);
trueSource = [caseData.true_x_m, caseData.true_y_m, caseData.true_Q_gps, caseData.true_H_m];
clean = gaussian_plume_concentration(trueSource, sensors, caseData.wind_speed_mps);

noisePattern = deterministic_noise_pattern(numel(clean));
observed = clean .* (1 + caseData.noise_fraction .* noisePattern);
observed = max(observed, 0);

observation = struct();
observation.data_type = caseData.data_type;
observation.name = caseData.name;
observation.sensors = sensors;
observation.clean_concentration = clean;
observation.observed_concentration = observed;
observation.true_source = trueSource;
observation.model_wind_speed_mps = caseData.model_wind_speed_mps;
observation.true_wind_speed_mps = caseData.wind_speed_mps;
observation.stability = caseData.stability;
observation.weight = caseData.weight;
observation.bounds.lb = [-80, -40, 5000, 0.5];
observation.bounds.ub = [40, 70, 25000, 8.0];
observation.note = 'Synthetic observation; not original article monitoring data.';
end

function pattern = deterministic_noise_pattern(n)
idx = (1:n)';
pattern = sin(1.7 .* idx) + 0.45 .* cos(0.9 .* idx);
pattern = pattern ./ max(abs(pattern));
end
