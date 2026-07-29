function observation = generate_npw_observation(caseData)
trueDeltaT_s = npw_delta_t( ...
    caseData.true_leak_position_m, ...
    caseData.true_wave_speed_mps, ...
    caseData.true_velocity_mps, ...
    caseData.pipeline_length_m, ...
    caseData.true_sync_offset_s);

observation = struct();
observation.data_type = caseData.data_type;
observation.name = caseData.name;
observation.scenario_class = caseData.scenario_class;
observation.pipeline_length_m = caseData.pipeline_length_m;
observation.true_leak_position_m = caseData.true_leak_position_m;
observation.validation_target_position_m = caseData.true_leak_position_m;
observation.true_wave_speed_mps = caseData.true_wave_speed_mps;
observation.true_velocity_mps = caseData.true_velocity_mps;
observation.true_sync_offset_s = caseData.true_sync_offset_s;
observation.true_delta_t_s = trueDeltaT_s;
observation.observed_delta_t_s = trueDeltaT_s + caseData.timing_noise_s;

observation.nominal_wave_speed_mps = caseData.nominal_wave_speed_mps;
observation.nominal_velocity_mps = caseData.nominal_velocity_mps;
observation.nominal_sync_offset_s = caseData.nominal_sync_offset_s;
observation.measured_wave_speed_mps = caseData.measured_wave_speed_mps;
observation.measured_velocity_mps = caseData.measured_velocity_mps;
observation.measured_sync_offset_s = caseData.measured_sync_offset_s;
observation.timing_noise_s = caseData.timing_noise_s;
observation.weight = caseData.weight;
observation.note = caseData.note;

observation.timing_scale_s = max(0.01, 2.0 * abs(caseData.timing_noise_s) + 0.015);
observation.wave_speed_sigma_mps = 0.035 * observation.nominal_wave_speed_mps;
observation.velocity_sigma_mps = 0.08 * observation.nominal_velocity_mps;
observation.sync_sigma_s = 0.25;
observation.location_sigma_m = 0.005 * observation.pipeline_length_m;
observation.bounds.lb = [0, 0.90 * observation.nominal_wave_speed_mps, 0.60 * observation.nominal_velocity_mps, -2.0];
observation.bounds.ub = [observation.pipeline_length_m, 1.10 * observation.nominal_wave_speed_mps, 1.20 * observation.nominal_velocity_mps, 2.0];
end
