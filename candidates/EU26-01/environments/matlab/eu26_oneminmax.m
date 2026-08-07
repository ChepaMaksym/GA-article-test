function point = eu26_oneminmax(bits)
%EU26_ONEMINMAX Exact OneMinMax objective pair [ones, zeros].

if isstring(bits) && isscalar(bits)
    bits = char(bits);
end
if ischar(bits)
    if isempty(bits) || any(bits ~= '0' & bits ~= '1')
        error('EU26:Bits', 'bit string must be non-empty and binary');
    end
    bits = double(bits - '0');
end
if ~isnumeric(bits) || isempty(bits) || ~isvector(bits) || ...
        any(~isfinite(bits)) || any(bits ~= 0 & bits ~= 1)
    error('EU26:Bits', 'bits must be a non-empty finite binary vector');
end
bits = bits(:).';
ones_count = sum(bits);
point = [ones_count, numel(bits) - ones_count];
end
