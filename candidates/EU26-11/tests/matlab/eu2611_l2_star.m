function value = eu2611_l2_star(points)
% Independent L2-star equation for EU26-11.

if isempty(points) || ndims(points) ~= 2
    error('EU2611:Shape', 'Point matrix must be nonempty and two-dimensional.');
end
if any(~isfinite(points(:))) || any(points(:) < 0) || any(points(:) > 1)
    error('EU2611:Range', 'Coordinates must be finite and in [0, 1].');
end

[count, dimension] = size(points);
sum_second = 0.0;
comp_second = 0.0;
for row = 1:count
    term = prod(1.0 - points(row, :) .^ 2);
    adjusted = term - comp_second;
    updated = sum_second + adjusted;
    comp_second = (updated - sum_second) - adjusted;
    sum_second = updated;
end

sum_third = 0.0;
comp_third = 0.0;
for left = 1:count
    for right = 1:count
        term = prod(1.0 - max(points(left, :), points(right, :)));
        adjusted = term - comp_third;
        updated = sum_third + adjusted;
        comp_third = (updated - sum_third) - adjusted;
        sum_third = updated;
    end
end

squared = 3.0 ^ (-dimension) ...
    - (2.0 ^ (1 - dimension) / count) * sum_second ...
    + sum_third / (count * count);
if ~isfinite(squared) || squared <= 0.0
    error('EU2611:Numeric', 'L2-star squared must be finite and positive.');
end
value = sqrt(squared);
end
