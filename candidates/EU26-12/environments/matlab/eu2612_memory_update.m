function result = eu2612_memory_update(old_fitness, new_fitness, successful_F, successful_CR)
% Released strict-success weighted arithmetic F/CR memory transition.
counts = [numel(old_fitness), numel(new_fitness), numel(successful_F), numel(successful_CR)];
if any(counts ~= counts(1)) || counts(1) == 0
    error('EU2612:MemoryShape', 'Memory vectors must have equal non-zero length.');
end
vectors = [old_fitness(:); new_fitness(:); successful_F(:); successful_CR(:)];
if any(~isfinite(vectors))
    error('EU2612:MemoryFinite', 'Memory inputs must be finite.');
end
if any(successful_F <= 0 | successful_F > 1) || any(successful_CR < 0 | successful_CR > 1)
    error('EU2612:MemoryRange', 'F or CR is outside the released domain.');
end
indices = find(new_fitness < old_fitness);
if isempty(indices)
    error('EU2612:NoSuccess', 'At least one strict improvement is required.');
end
deltas = abs(old_fitness(indices) - new_fitness(indices));
if sum(deltas) <= 0
    error('EU2612:ZeroWeight', 'Strict-success weight sum must be positive.');
end
weights = deltas / sum(deltas);
result = struct( ...
    'successful_indices', indices - 1, ...
    'weights', weights, ...
    'F', sum(weights .* successful_F(indices)), ...
    'CR', sum(weights .* successful_CR(indices)));
end
