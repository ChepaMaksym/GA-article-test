function deltaT_s = npw_delta_t(leakPosition_m, waveSpeed_mps, fluidVelocity_mps, pipelineLength_m, syncOffset_s)
if nargin < 5
    syncOffset_s = 0;
end

validate_npw_inputs(leakPosition_m, waveSpeed_mps, fluidVelocity_mps, pipelineLength_m);
deltaT_s = leakPosition_m ./ (waveSpeed_mps - fluidVelocity_mps) ...
    - (pipelineLength_m - leakPosition_m) ./ (waveSpeed_mps + fluidVelocity_mps) ...
    + syncOffset_s;
end
