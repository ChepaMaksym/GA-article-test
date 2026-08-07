function value = bandit_objective(name, x)
%BANDIT_OBJECTIVE Independent Appendix A objective-function port.

if ~(ischar(name) || (isstring(name) && isscalar(name)))
    error('banditverify:InvalidName', 'Objective name must be text.');
end
if ~isnumeric(x) || ~isreal(x) || ~isvector(x) || isempty(x) || any(~isfinite(x(:)))
    error('banditverify:InvalidVector', ...
        'Objective input must be a nonempty finite real vector.');
end
x = double(x(:).');
name = lower(char(name));
d = numel(x);

switch name
    case 'ackley'
        value = -20 * exp(-0.2 * sqrt(sum(x .^ 2) / d)) ...
            - exp(sum(cos(2 * pi * x)) / d) + 20 + exp(1);
    case 'griewank'
        paper_index = 1:d;
        value = sum(x .^ 2) / 4000 ...
            - prod(cos(x ./ sqrt(paper_index))) + 1;
    case 'rastrigin'
        value = 10 * d + sum(x .^ 2 - 10 * cos(2 * pi * x));
    case 'rosenbrock'
        if d < 2
            error('banditverify:InvalidDimension', ...
                'Rosenbrock requires at least two values.');
        end
        left = x(1:end-1);
        right = x(2:end);
        value = sum(100 * (right - left .^ 2) .^ 2 + (left - 1) .^ 2);
    case 'sphere'
        value = sum(x .^ 2);
    case 'linear'
        value = sum(x);
    otherwise
        error('banditverify:UnknownObjective', 'Unknown objective: %s', name);
end

if ~isfinite(value)
    error('banditverify:NonFiniteResult', ...
        'Objective produced a non-finite result.');
end
end
