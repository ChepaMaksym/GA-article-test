function value = eu2609_round_ties_even(input_value)
% Independent positive nearest/ties-to-even rule used by Python source.
if ~isnumeric(input_value) || ~isscalar(input_value) || ~isfinite(input_value) ...
        || input_value <= 0
    error('EU2609:Control', 'input_value must be a finite positive scalar');
end
lower_value = floor(input_value);
fraction = input_value - lower_value;
if fraction < 0.5
    value = lower_value;
elseif fraction > 0.5
    value = lower_value + 1;
elseif mod(lower_value, 2) == 0
    value = lower_value;
else
    value = lower_value + 1;
end
end
