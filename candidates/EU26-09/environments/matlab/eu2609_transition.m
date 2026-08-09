function lambda_next = eu2609_transition(lambda_real, success, update_factor, lambda_max)
% Apply success, cap-reset failure, or fourth-root failure transition.
if ~isnumeric(lambda_real) || ~isscalar(lambda_real) || ~isfinite(lambda_real) ...
        || lambda_real <= 0
    error('EU2609:Control', 'lambda_real must be finite and positive');
end
if ~islogical(success) || ~isscalar(success)
    error('EU2609:Control', 'success must be a logical scalar');
end
if ~isnumeric(update_factor) || ~isscalar(update_factor) ...
        || ~isfinite(update_factor) || update_factor <= 1
    error('EU2609:Control', 'update_factor must be greater than one');
end
if ~isnumeric(lambda_max) || ~isscalar(lambda_max) || ~isfinite(lambda_max) ...
        || lambda_max <= 0 || lambda_real > lambda_max
    error('EU2609:Control', 'lambda_max or lambda_real is invalid');
end

if success
    updated = lambda_real / update_factor;
elseif lambda_real == lambda_max
    updated = 1;
else
    updated = lambda_real * update_factor^(1/4);
end
lambda_next = min(max(updated, 1), lambda_max);
end
