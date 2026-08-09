function values = eu2612_transform_f(memory, cauchy_sequences)
% Released F transform: redraw non-positive candidates and cap above one.
if ~isscalar(memory) || ~isfinite(memory) || memory <= 0 || memory > 1
    error('EU2612:FMemory', 'F memory must be one finite value in (0,1].');
end
if ~iscell(cauchy_sequences) || isempty(cauchy_sequences)
    error('EU2612:FDraws', 'F draw sequences must be a non-empty cell array.');
end
values = zeros(1, numel(cauchy_sequences));
for individual = 1:numel(cauchy_sequences)
    sequence = cauchy_sequences{individual};
    if isempty(sequence) || any(~isfinite(sequence))
        error('EU2612:FSequence', 'Each F draw sequence must be non-empty and finite.');
    end
    accepted = false;
    for draw = sequence
        candidate = memory + 0.1 * draw;
        if candidate > 0
            values(individual) = min(candidate, 1);
            accepted = true;
            break;
        end
    end
    if ~accepted
        error('EU2612:FNoPositive', 'An F sequence never produced a positive draw.');
    end
end
end
