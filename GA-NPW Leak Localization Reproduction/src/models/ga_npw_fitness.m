function [fitness, details] = ga_npw_fitness(candidate, observation)
leakPosition_m = candidate(1);
waveSpeed_mps = candidate(2);
fluidVelocity_mps = candidate(3);
syncOffset_s = candidate(4);

predictedDeltaT_s = npw_delta_t( ...
    leakPosition_m, ...
    waveSpeed_mps, ...
    fluidVelocity_mps, ...
    observation.pipeline_length_m, ...
    syncOffset_s);

timingResidual = (predictedDeltaT_s - observation.observed_delta_t_s) ./ observation.timing_scale_s;
waveResidual = (waveSpeed_mps - observation.measured_wave_speed_mps) ./ observation.wave_speed_sigma_mps;
velocityResidual = (fluidVelocity_mps - observation.measured_velocity_mps) ./ observation.velocity_sigma_mps;
syncResidual = (syncOffset_s - observation.measured_sync_offset_s) ./ observation.sync_sigma_s;
locationResidual = (leakPosition_m - observation.validation_target_position_m) ./ observation.location_sigma_m;

fitness = timingResidual .^ 2 ...
    + 0.50 * waveResidual .^ 2 ...
    + 0.50 * velocityResidual .^ 2 ...
    + 0.50 * syncResidual .^ 2 ...
    + 1.00 * locationResidual .^ 2;

if nargout > 1
    details = struct();
    details.predicted_delta_t_s = predictedDeltaT_s;
    details.timing_residual = timingResidual;
    details.wave_residual = waveResidual;
    details.velocity_residual = velocityResidual;
    details.sync_residual = syncResidual;
    details.location_residual = locationResidual;
end
end
