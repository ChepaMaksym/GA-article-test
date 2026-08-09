function value = eu2612_round_ties_even(input_value)
% Explicit non-negative nearest-integer rounding with half ties to even.
if ~isscalar(input_value) || ~isnumeric(input_value) || ~isfinite(input_value) || input_value < 0
    error('EU2612:RoundDomain', 'Input must be one finite non-negative scalar.');
end
lower = floor(input_value);
fraction = input_value - lower;
if fraction < 0.5
    value = lower;
elseif fraction > 0.5
    value = lower + 1;
elseif mod(lower, 2) == 0
    value = lower;
else
    value = lower + 1;
end
end
