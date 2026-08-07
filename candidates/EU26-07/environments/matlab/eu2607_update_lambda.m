function lambda_after = eu2607_update_lambda( ...
        lambda_real, strict_success, update_factor, lambda_max, reset)
%EU2607_UPDATE_LAMBDA Apply shrink/reset/grow to the pre-generation lambda.
%
% A strict success shrinks lambda by F.  On failure, reset occurs only when
% the current real lambda already equals the cap.  A growth step that merely
% reaches the cap therefore does not reset until a later failed generation.

if nargin < 5
    reset = true;
end
if ~is_scalar_real(lambda_real) || ~is_scalar_real(lambda_max) ...
        || lambda_real < 1 || lambda_max < 1 || lambda_real > lambda_max
    error('EU2607:BadLambda', ...
        'Require finite values satisfying 1 <= lambda_real <= lambda_max');
end
if ~is_scalar_real(update_factor) || update_factor <= 1
    error('EU2607:BadUpdateFactor', 'update_factor must be finite and > 1');
end
if ~islogical(strict_success) || ~isscalar(strict_success)
    error('EU2607:BadSuccessFlag', 'strict_success must be a logical scalar');
end
if ~islogical(reset) || ~isscalar(reset)
    error('EU2607:BadResetFlag', 'reset must be a logical scalar');
end

value = double(lambda_real);
cap = double(lambda_max);
factor = double(update_factor);
if strict_success
    lambda_after = max(value / factor, 1.0);
elseif reset && value == cap
    lambda_after = 1.0;
else
    lambda_after = min(value * factor ^ 0.25, cap);
end
end

function tf = is_scalar_real(value)
tf = isnumeric(value) && ~islogical(value) && isreal(value) ...
    && isscalar(value) && isfinite(double(value));
end
