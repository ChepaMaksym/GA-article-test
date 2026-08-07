function value = bandit_reward(semantics, parent_error, child_error)
%BANDIT_REWARD Evaluate one frozen P1/P2/P3 interpretation.

if ~(ischar(semantics) || (isstring(semantics) && isscalar(semantics)))
    error('banditverify:InvalidSemantics', 'Reward semantics must be text.');
end
validate_errors(parent_error, child_error);
parent_error = double(parent_error(:));
child_error = double(child_error(:));
semantics = char(semantics);

switch semantics
    case 'P1'
        terms = parent_error - child_error;
    case {'P2', 'P3'}
        if any(parent_error <= -1) || any(child_error <= -1)
            error('banditverify:LogDomain', ...
                '%s requires every error entry to be greater than -1.', semantics);
        end
        if strcmp(semantics, 'P2')
            terms = log1p(parent_error) - log1p(child_error);
        else
            terms = log1p(child_error) - log1p(parent_error);
        end
    otherwise
        error('banditverify:InvalidSemantics', ...
            'Reward semantics must be exactly P1, P2, or P3.');
end
value = mean(terms);
end

function validate_errors(parent_error, child_error)
if ~isnumeric(parent_error) || ~isnumeric(child_error) ...
        || ~isreal(parent_error) || ~isreal(child_error) ...
        || ~isvector(parent_error) || ~isvector(child_error) ...
        || isempty(parent_error) || numel(parent_error) ~= numel(child_error) ...
        || any(~isfinite(parent_error(:))) || any(~isfinite(child_error(:)))
    error('banditverify:InvalidErrors', ...
        'Parent and child errors must be equal-length nonempty finite vectors.');
end
end
