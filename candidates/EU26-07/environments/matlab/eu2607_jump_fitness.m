function [value, is_optimum] = eu2607_jump_fitness(bit_string, n, k)
%EU2607_JUMP_FITNESS Evaluate the frozen Jump_k maximization objective.
%
% BIT_STRING is the non-negative integer encoding of an n-bit string.  The
% all-ones string has value n+k; strings with at most n-k ones have value
% k+ones; the intervening gap has value n-ones.

validate_problem(n, k);
validate_bit_string(bit_string, n);

ones_count = sum(double(bitget(uint64(bit_string), 1:double(n))));
if ones_count <= double(n - k) || ones_count == double(n)
    value = double(k) + ones_count;
else
    value = double(n) - ones_count;
end
is_optimum = value == double(n + k);
end

function validate_problem(n, k)
if ~is_scalar_integer(n) || n < 11
    error('EU2607:BadProblem', 'n must be an integer greater than or equal to 11');
end
% MATLAB/Octave JSON and ordinary numeric literals are binary64.  Keeping
% n at most 53 makes every accepted encoded bit string exactly representable.
if double(n) > 53
    error('EU2607:BadProblem', ...
        'The MATLAB/Octave encoded-bit-string layer requires n <= 53');
end
if ~is_scalar_integer(k) || k < 1 || k >= n
    error('EU2607:BadProblem', 'k must be an integer in [1,n)');
end
end

function validate_bit_string(bit_string, n)
if ~is_scalar_integer(bit_string) || bit_string < 0 ...
        || double(bit_string) >= 2 ^ double(n)
    error('EU2607:BadBitString', ...
        'bit_string must be an integer in the n-bit domain');
end
end

function tf = is_scalar_integer(value)
tf = isnumeric(value) && ~islogical(value) && isreal(value) ...
    && isscalar(value) && isfinite(double(value)) ...
    && double(value) == fix(double(value));
end
