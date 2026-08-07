function value = bandit_printed_eq2_literal(parent_error, child_error)
%BANDIT_PRINTED_EQ2_LITERAL Exhibit the printed 0..m divided-by-m conflict.

if ~isnumeric(parent_error) || ~isnumeric(child_error) ...
        || ~isvector(parent_error) || ~isvector(child_error) ...
        || isempty(parent_error) || numel(parent_error) ~= numel(child_error) ...
        || any(~isfinite(parent_error(:))) || any(~isfinite(child_error(:)))
    error('banditverify:InvalidErrors', ...
        'Parent and child errors must be equal-length nonempty finite vectors.');
end
if any(parent_error(:) <= -1) || any(child_error(:) <= -1)
    error('banditverify:LogDomain', ...
        'The printed log expression requires entries greater than -1.');
end
divisor = numel(parent_error) - 1;
if divisor == 0
    error('banditverify:PrintedEq2Singular', ...
        'Printed Eq. (2) divides a one-entry vector by m=0.');
end
value = sum(log1p(parent_error(:)) - log1p(child_error(:))) / divisor;
end
