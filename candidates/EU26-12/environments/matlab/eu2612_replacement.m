function result = eu2612_replacement(parent_fitness, offspring_fitness)
% Parent survives only on strict parent_fitness < offspring_fitness.
if numel(parent_fitness) ~= numel(offspring_fitness) || isempty(parent_fitness)
    error('EU2612:ReplacementShape', 'Replacement vectors must have equal non-zero length.');
end
if any(~isfinite(parent_fitness)) || any(~isfinite(offspring_fitness))
    error('EU2612:ReplacementFinite', 'Replacement fitness must be finite.');
end
sources = cell(1, numel(parent_fitness));
for index = 1:numel(parent_fitness)
    if parent_fitness(index) < offspring_fitness(index)
        sources{index} = 'parent';
    else
        sources{index} = 'offspring';
    end
end
result = struct( ...
    'sources', {sources}, ...
    'improved', offspring_fitness < parent_fitness);
end
