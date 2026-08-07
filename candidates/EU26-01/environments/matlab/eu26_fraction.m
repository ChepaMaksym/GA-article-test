function value = eu26_fraction(input_value)
%EU26_FRACTION Parse an exact fixture rational into a finite scalar double.

if isnumeric(input_value) && isscalar(input_value) && isfinite(input_value)
    value = double(input_value);
    return;
end
if isstring(input_value) && isscalar(input_value)
    input_value = char(input_value);
end
if ~ischar(input_value) || isempty(input_value)
    error('EU26:Fraction', 'value must be a finite scalar or rational string');
end
parts = strsplit(input_value, '/');
if numel(parts) == 1
    value = str2double(parts{1});
elseif numel(parts) == 2
    numerator = str2double(parts{1});
    denominator = str2double(parts{2});
    if denominator == 0
        error('EU26:Fraction', 'rational denominator cannot be zero');
    end
    value = numerator / denominator;
else
    value = NaN;
end
if ~isscalar(value) || ~isfinite(value)
    error('EU26:Fraction', 'value is not a finite rational');
end
end
