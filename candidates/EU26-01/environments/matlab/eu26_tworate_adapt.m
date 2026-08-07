function result = eu26_tworate_adapt(population, children, r, q, n)
%EU26_TWORATE_ADAPT Paper Algorithm-2/source transition on explicit children.

if ~isnumeric(population) || isempty(population) || size(population, 2) ~= 2 || ...
        size(unique(population, 'rows'), 1) ~= size(population, 1)
    error('EU26:Population', 'population must be a unique N-by-2 matrix');
end
if ~isnumeric(children) || isempty(children) || size(children, 2) ~= 2 || ...
        mod(size(children, 1), 2) ~= 0 || any(~isfinite(children(:)))
    error('EU26:Children', 'children must be a finite even-size N-by-2 matrix');
end
if ~isnumeric(n) || ~isscalar(n) || ~isfinite(n) || n <= 0 || n ~= fix(n)
    error('EU26:Dimension', 'n must be a positive integer');
end
r = eu26_fraction(r);
q = eu26_fraction(q);
if r < 0.5 || r > n / 4
    error('EU26:Strength', 'r lies outside [1/2,n/4]');
end
if q < 0 || q > 1
    error('EU26:Tape', 'q must lie in [0,1]');
end

scores = zeros(1, size(children, 1));
for i = 1:size(children, 1)
    scores(i) = eu26_hypervolume2d([population; children(i, :)], [-1, -1]);
end
[~, winner_one_based] = max(scores);
winner_zero_based = winner_one_based - 1;
half = size(children, 1) / 2;
if winner_zero_based < half
    winner_group = 'low';
    s = 3 / 4;
else
    winner_group = 'high';
    s = 1 / 4;
end
if q <= s
    decision = 'halve';
    r_after = max(r / 2, 0.5);
else
    decision = 'double';
    r_after = min(2 * r, n / 4);
end
result = struct( ...
    'scores', scores, ...
    'winner_index', winner_zero_based, ...
    'winner_group', winner_group, ...
    's', s, ...
    'q', q, ...
    'decision', decision, ...
    'r_before', r, ...
    'r_after', r_after);
end
