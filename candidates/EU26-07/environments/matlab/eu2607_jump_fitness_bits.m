function [values, is_optimum] = eu2607_jump_fitness_bits(bit_strings, n, k)
%EU2607_JUMP_FITNESS_BITS Evaluate Jump_k on logical bit-vector rows.
%
% Unlike the legacy encoded-integer oracle, this representation supports the
% paper's n=60 experiment and larger dimensions without binary64 limits.

validate_problem(n, k);
bits = require_bit_matrix(bit_strings, n);
ones_count = sum(double(bits), 2);
values = zeros(size(ones_count));
regular = ones_count <= double(n - k) | ones_count == double(n);
values(regular) = double(k) + ones_count(regular);
values(~regular) = double(n) - ones_count(~regular);
is_optimum = values == double(n + k);
end

function validate_problem(n, k)
if ~is_scalar_integer(n) || n < 11
    error('EU2607:BadProblem', 'n must be an integer greater than or equal to 11');
end
if ~is_scalar_integer(k) || k < 1 || k >= n
    error('EU2607:BadProblem', 'k must be an integer in [1,n)');
end
end

function bits = require_bit_matrix(value, n)
if islogical(value)
    bits = value;
elseif isnumeric(value) && isreal(value) && all(isfinite(double(value(:)))) ...
        && all(double(value(:)) == 0 | double(value(:)) == 1)
    bits = logical(value);
else
    error('EU2607:BadBitMatrix', ...
        'bit_strings must be a logical or numeric zero-one vector/matrix');
end
if isvector(bits)
    bits = reshape(bits, 1, []);
end
if ndims(bits) ~= 2 || size(bits, 1) < 1 || size(bits, 2) ~= double(n)
    error('EU2607:BadBitMatrix', ...
        'bit_strings must contain one or more rows with exactly n columns');
end
end

function tf = is_scalar_integer(value)
tf = isnumeric(value) && ~islogical(value) && isreal(value) ...
    && isscalar(value) && isfinite(double(value)) ...
    && double(value) == fix(double(value));
end
