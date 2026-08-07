function probabilities = eu2605_probability_update(successes, crossovers)
%EU2605_PROBABILITY_UPDATE Complete-positive-denominator formula profile.
% This is a formula oracle only. A zero per-type denominator is undefined by
% the paper/thesis sources and therefore fails closed.

validate_integer_row(successes, 'successes');
validate_integer_row(crossovers, 'crossovers');
if numel(successes) ~= 4 || numel(crossovers) ~= 4
    error('EU2605:BadProbabilityInput', ...
        'successes and crossovers must each contain exactly four values');
end
if any(crossovers <= 0)
    error('EU2605:BadProbabilityInput', ...
        'every crossover denominator must be positive');
end
if any(successes < 0) || any(successes > crossovers)
    error('EU2605:BadProbabilityInput', ...
        'successes must satisfy 0 <= successes <= crossovers');
end

rates = successes ./ crossovers;
if all(rates == 0)
    probabilities = 0.25 * ones(1, 4);
else
    probabilities = 0.10 + 0.60 .* rates ./ sum(rates);
end
if abs(sum(probabilities) - 1) > 1e-12 ...
        || any(probabilities < 0.10 - 1e-12) ...
        || any(probabilities > 0.70 + 1e-12)
    error('EU2605:InternalInvariant', ...
        'probability update violated the frozen simplex or bounds');
end
end

function validate_integer_row(values, name)
if ~isnumeric(values) || ~isreal(values) || ~isrow(values) ...
        || any(~isfinite(values)) || any(values ~= fix(values))
    error('EU2605:BadProbabilityInput', ...
        '%s must be a finite integer row vector', name);
end
end
