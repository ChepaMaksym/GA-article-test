function leakPosition_m = npw_position_from_delta_t(deltaT_s, waveSpeed_mps, fluidVelocity_mps, pipelineLength_m, syncOffset_s)
if nargin < 5
    syncOffset_s = 0;
end

validate_npw_inputs(0.5 * pipelineLength_m, waveSpeed_mps, fluidVelocity_mps, pipelineLength_m);
effectiveDeltaT_s = deltaT_s - syncOffset_s;
denominator = 1 ./ (waveSpeed_mps - fluidVelocity_mps) + 1 ./ (waveSpeed_mps + fluidVelocity_mps);
leakPosition_m = (effectiveDeltaT_s + pipelineLength_m ./ (waveSpeed_mps + fluidVelocity_mps)) ./ denominator;
leakPosition_m = min(max(leakPosition_m, 0), pipelineLength_m);
end
