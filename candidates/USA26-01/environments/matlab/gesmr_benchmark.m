function values = gesmr_benchmark(name, population)
%GESMR_BENCHMARK Direct analytic minimization objectives, evaluated row-wise.

if ~isnumeric(population) || ndims(population) ~= 2 || size(population, 2) < 1
    error('gesmr:BadPopulation', 'population must be a numeric matrix');
end
if any(~isfinite(population(:)))
    error('gesmr:BadPopulation', 'population must be finite');
end

key = lower(strtrim(char(name)));
d = size(population, 2);
switch key
    case 'sphere'
        values = sum(population .^ 2, 2);
    case 'ackley'
        mean_square = mean(population .^ 2, 2);
        mean_cosine = mean(cos(2 * pi * population), 2);
        values = -20 * exp(-0.2 * sqrt(mean_square)) ...
            - exp(mean_cosine) + 20 + exp(1);
    case 'griewank'
        divisors = sqrt(1:d);
        values = sum(population .^ 2, 2) / 4000 ...
            - prod(cos(bsxfun(@rdivide, population, divisors)), 2) + 1;
    case 'rastrigin'
        values = 10 * d + sum( ...
            population .^ 2 - 10 * cos(2 * pi * population), 2);
    case 'rosenbrock'
        if d < 2
            error('gesmr:BadDimension', 'Rosenbrock requires dimension >= 2');
        end
        left = population(:, 1:end-1);
        right = population(:, 2:end);
        values = sum(100 * (right - left .^ 2) .^ 2 + (1 - left) .^ 2, 2);
    otherwise
        error('gesmr:UnknownBenchmark', 'Unknown benchmark: %s', char(name));
end
values = values(:);
end
