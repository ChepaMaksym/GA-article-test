function result = eu2607_controls(lambda_real, n, profile, crossover_coefficient)
%EU2607_CONTROLS Derive m, p=lambda/n, and c=1/lambda for Algorithm 3.

if nargin < 4
    crossover_coefficient = 1.0;
end
if ~is_scalar_integer(n) || n < 11
    error('EU2607:BadProblem', 'n must be an integer >= 11');
end
if ~is_scalar_real(lambda_real) || lambda_real < 1 || lambda_real > n
    error('EU2607:BadLambda', 'lambda_real must be finite and lie in [1,n]');
end
if ~is_scalar_real(crossover_coefficient) || crossover_coefficient ~= 1.0
    error('EU2607:BadCrossoverCoefficient', ...
        'Algorithm 3 requires crossover coefficient 1');
end

value = double(lambda_real);
result = struct();
result.lambda_real = value;
result.offspring_count = eu2607_round_lambda(value, profile);
result.mutation_probability = value / double(n);
result.crossover_probability = 1.0 / value;
end

function tf = is_scalar_integer(value)
tf = isnumeric(value) && ~islogical(value) && isreal(value) ...
    && isscalar(value) && isfinite(double(value)) ...
    && double(value) == fix(double(value));
end

function tf = is_scalar_real(value)
tf = isnumeric(value) && ~islogical(value) && isreal(value) ...
    && isscalar(value) && isfinite(double(value));
end
