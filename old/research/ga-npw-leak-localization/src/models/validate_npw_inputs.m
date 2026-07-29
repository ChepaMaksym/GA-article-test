function validate_npw_inputs(leakPosition_m, waveSpeed_mps, fluidVelocity_mps, pipelineLength_m)
if any(pipelineLength_m <= 0)
    error('Pipeline length must be positive.');
end
if any(waveSpeed_mps <= abs(fluidVelocity_mps))
    error('Wave speed must be larger than absolute fluid velocity.');
end
if any(leakPosition_m < 0) || any(leakPosition_m > pipelineLength_m)
    error('Leak position must be inside the pipeline.');
end
end
