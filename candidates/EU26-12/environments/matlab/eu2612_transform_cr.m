function values = eu2612_transform_cr(memory, normal_z)
% Released CR transform: memory + 0.1*z, clipped to [0,1].
if ~isscalar(memory) || ~isfinite(memory) || memory < 0 || memory > 1
    error('EU2612:CRMemory', 'CR memory must be one finite value in [0,1].');
end
if isempty(normal_z) || any(~isfinite(normal_z))
    error('EU2612:CRDraws', 'CR draws must be a non-empty finite vector.');
end
values = min(max(memory + 0.1 * normal_z, 0), 1);
end
