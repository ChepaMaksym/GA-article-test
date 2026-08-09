function rounded = eu2616_round_best_fitness(value)
% Mirror the Java float/multiply/Math.round/divide sequence in Alg.java.
if ~isscalar(value) || ~isnumeric(value) || ~isfinite(value)
    error('EU2616:Input', 'best fitness must be a finite numeric scalar');
end
current = single(value);
if ~isfinite(current)
    error('EU2616:Input', 'best fitness is outside Java float range');
end
current = single(current * single(10000));
current = single(floor(double(current) + 0.5));
rounded = single(current / single(10000));
end
