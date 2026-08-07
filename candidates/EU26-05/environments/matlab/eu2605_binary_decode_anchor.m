function value = eu2605_binary_decode_anchor( ...
    bits, lower_bound, upper_bound, bit_order, endpoint_convention)
%EU2605_BINARY_DECODE_ANCHOR Explicit-convention interface anchor.
% Endianness and endpoint mapping are not specified by the publication, so
% both are mandatory inputs and this function is not a paper-faithful decoder.

validate_bits(bits, 'bits', 1);
if ~isnumeric(lower_bound) || ~isreal(lower_bound) ...
        || ~isscalar(lower_bound) || ~isfinite(lower_bound) ...
        || ~isnumeric(upper_bound) || ~isreal(upper_bound) ...
        || ~isscalar(upper_bound) || ~isfinite(upper_bound) ...
        || lower_bound >= upper_bound
    error('EU2605:BadDecodeInput', ...
        'decode bounds must be finite increasing real scalars');
end
if ~ischar(bit_order) || ~isrow(bit_order) ...
        || ~ischar(endpoint_convention) || ~isrow(endpoint_convention)
    error('EU2605:BadDecodeInput', ...
        'decode conventions must be supplied as character rows');
end
if ~strcmp(endpoint_convention, 'closed_linear')
    error('EU2605:BadDecodeInput', ...
        'endpoint_convention must be closed_linear');
end

if strcmp(bit_order, 'msb_first')
    weights = 2 .^ ((numel(bits) - 1):-1:0);
elseif strcmp(bit_order, 'lsb_first')
    weights = 2 .^ (0:(numel(bits) - 1));
else
    error('EU2605:BadDecodeInput', ...
        'bit_order must be msb_first or lsb_first');
end
integer_value = sum((double(bits) - double('0')) .* weights);
maximum_value = 2 ^ numel(bits) - 1;
value = lower_bound + (upper_bound - lower_bound) ...
    * integer_value / maximum_value;
end

function validate_bits(bits, name, minimum_length)
if ~ischar(bits) || ~isrow(bits) || numel(bits) < minimum_length ...
        || any(bits ~= '0' & bits ~= '1')
    error('EU2605:BadDecodeInput', '%s must be a binary character row', name);
end
end
