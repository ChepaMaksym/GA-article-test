function child = eu2607_crossover_mask(parent, mutant, n, positions)
%EU2607_CROSSOVER_MASK Take mutant bits at a supplied Bernoulli mask.
%
% Positions are zero-based from the least-significant bit.  The probability
% that produced this realized mask belongs to the named algorithm profile;
% this function verifies the deterministic biased-uniform crossover formula.

validate_encoded_bit_string(parent, n, 'parent');
validate_encoded_bit_string(mutant, n, 'mutant');
positions = validate_positions(positions, n);
value = uint64(parent);
mutant_value = uint64(mutant);
for position_index = 1:numel(positions)
    bit_position = positions(position_index) + 1;
    value = bitset(value, bit_position, bitget(mutant_value, bit_position));
end
child = double(value);
end

function positions = validate_positions(positions, n)
if ~isnumeric(positions) || islogical(positions) || ~isreal(positions) ...
        || ~(isempty(positions) || isvector(positions))
    error('EU2607:BadPositions', 'positions must be a real numeric vector');
end
positions = reshape(double(positions), 1, []);
if any(~isfinite(positions)) || any(positions ~= fix(positions)) ...
        || any(positions < 0) || any(positions >= double(n)) ...
        || numel(unique(positions)) ~= numel(positions)
    error('EU2607:BadPositions', ...
        'positions must be distinct zero-based indices in the n-bit domain');
end
end

function validate_encoded_bit_string(value, n, label)
if ~isnumeric(n) || islogical(n) || ~isreal(n) || ~isscalar(n) ...
        || ~isfinite(double(n)) || double(n) ~= fix(double(n)) ...
        || n < 11 || n > 53
    error('EU2607:BadProblem', 'n must be an integer in [11,53]');
end
if ~isnumeric(value) || islogical(value) || ~isreal(value) ...
        || ~isscalar(value) || ~isfinite(double(value)) ...
        || double(value) ~= fix(double(value)) || value < 0 ...
        || double(value) >= 2 ^ double(n)
    error('EU2607:BadBitString', '%s is outside the n-bit domain', label);
end
end
