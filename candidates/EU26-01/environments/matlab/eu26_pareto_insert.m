function result = eu26_pareto_insert(population, child)
%EU26_PARETO_INSERT Source-order Pareto replacement for maximization.

if ~isnumeric(population) || isempty(population) || size(population, 2) ~= 2 || ...
        any(~isfinite(population(:))) || size(unique(population, 'rows'), 1) ~= size(population, 1)
    error('EU26:Pareto', 'population must contain unique finite objective pairs');
end
if ~isnumeric(child) || ~isequal(size(child), [1, 2]) || any(~isfinite(child))
    error('EU26:Pareto', 'child must be one finite objective pair');
end
for i = 1:size(population, 1)
    if all(population(i, :) >= child) && any(population(i, :) > child)
        result = sortrows(population, 1);
        return;
    end
end
retained = true(size(population, 1), 1);
for i = 1:size(population, 1)
    if all(child >= population(i, :))
        retained(i) = false;
    end
end
result = unique([population(retained, :); child], 'rows');
result = sortrows(result, 1);
end
