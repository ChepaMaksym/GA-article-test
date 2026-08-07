function offspring_count = eu2607_round_lambda(lambda_real, profile)
%EU2607_ROUND_LAMBDA Apply one explicitly named EU26-07 rounding profile.
%
% paper_algorithm3 uses nearest-integer rounding with exact half values
% rounded upward.  Both author-artifact profiles reproduce Python's
% nearest-integer, ties-to-even rule.  No unnamed/default profile exists.

if ~is_scalar_real(lambda_real) || lambda_real < 1
    error('EU2607:BadLambda', 'lambda_real must be finite and >= 1');
end
profile = require_profile_name(profile);
value = double(lambda_real);

switch profile
    case 'paper_algorithm3'
        offspring_count = floor(value + 0.5);
    case {'artifact_generic', 'artifact_jump_optimized'}
        lower = floor(value);
        fraction = value - lower;
        if fraction < 0.5
            offspring_count = lower;
        elseif fraction > 0.5
            offspring_count = lower + 1;
        else
            % Python round() chooses the even neighbor at an exact tie.
            offspring_count = lower + mod(lower, 2);
        end
    otherwise
        % REQUIRE_PROFILE_NAME rejects this path; retain a fail-closed guard
        % so adding a profile name cannot silently inherit a rounding rule.
        error('EU2607:BadProfile', 'Unsupported EU26-07 profile');
end
offspring_count = max(1, offspring_count);
end

function profile = require_profile_name(profile)
if ischar(profile) && isrow(profile)
    % Already a character row vector.
elseif has_isstring() && isstring(profile) && isscalar(profile)
    profile = char(profile);
else
    error('EU2607:BadProfile', 'profile must be a scalar name');
end
allowed = { ...
    'paper_algorithm3', ...
    'artifact_generic', ...
    'artifact_jump_optimized'};
if ~any(strcmp(profile, allowed))
    error('EU2607:BadProfile', 'Unknown EU26-07 profile: %s', profile);
end
end

function tf = has_isstring()
tf = exist('isstring', 'builtin') ~= 0 || exist('isstring', 'file') ~= 0;
end

function tf = is_scalar_real(value)
tf = isnumeric(value) && ~islogical(value) && isreal(value) ...
    && isscalar(value) && isfinite(double(value));
end
