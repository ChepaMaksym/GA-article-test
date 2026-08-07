function volume = eu26_hypervolume2d(points, reference)
%EU26_HYPERVOLUME2D Exact 2-D maximization HV for integer-valued fixtures.

if nargin < 2
    reference = [-1, -1];
end
validate_points(points, 'points');
validate_points(reference, 'reference');
if size(reference, 1) ~= 1
    error('EU26:Reference', 'reference must contain one point');
end

front = unique(points, 'rows');
keep = true(size(front, 1), 1);
for i = 1:size(front, 1)
    for j = 1:size(front, 1)
        if i ~= j && all(front(j, :) >= front(i, :)) && ...
                any(front(j, :) > front(i, :))
            keep(i) = false;
            break;
        end
    end
end
front = sortrows(front(keep, :), 1);
if any(front(:, 1) < reference(1)) || any(front(:, 2) < reference(2))
    error('EU26:Reference', 'all points must weakly dominate the reference');
end

volume = 0;
last_x = reference(1);
for i = 1:size(front, 1)
    width = front(i, 1) - last_x;
    if width < 0
        error('EU26:Hypervolume', 'front order produced a negative width');
    end
    volume = volume + width * (front(i, 2) - reference(2));
    last_x = front(i, 1);
end
end

function validate_points(points, label)
if ~isnumeric(points) || isempty(points) || size(points, 2) ~= 2 || ...
        any(~isfinite(points(:))) || any(points(:) ~= fix(points(:)))
    error('EU26:Point', '%s must be a non-empty finite integer N-by-2 matrix', label);
end
end
