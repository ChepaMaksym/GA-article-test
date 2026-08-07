function result = eu2605_objective_interface_anchor( ...
    chromosome, objective_handle, bit_order, endpoint_convention, ...
    claimed_authenticated_cec)
%EU2605_OBJECTIVE_INTERFACE_ANCHOR Test-only 30x20 decode/objective interface.
% This function intentionally contains no CEC-2017 objective.

if nargin < 5
    claimed_authenticated_cec = false;
end
if ~ischar(chromosome) || ~isrow(chromosome) ...
        || numel(chromosome) ~= 600 ...
        || any(chromosome ~= '0' & chromosome ~= '1')
    error('EU2605:BadObjectiveAnchor', ...
        'the selected interface requires exactly 600 binary characters');
end
if ~isa(objective_handle, 'function_handle')
    error('EU2605:BadObjectiveAnchor', ...
        'objective_handle must be an injected function handle');
end
if ~islogical(claimed_authenticated_cec) || ~isscalar(claimed_authenticated_cec)
    error('EU2605:BadObjectiveAnchor', ...
        'claimed_authenticated_cec must be a logical scalar');
end
if claimed_authenticated_cec
    error('EU2605:BadObjectiveAnchor', ...
        'v1 has no authenticated CEC-2017 implementation');
end

coordinates = zeros(1, 30);
for coordinate_index = 1:30
    first = (coordinate_index - 1) * 20 + 1;
    block = chromosome(first:(first + 19));
    coordinates(coordinate_index) = eu2605_binary_decode_anchor( ...
        block, -100, 100, bit_order, endpoint_convention);
end
value = objective_handle(coordinates);
if ~isnumeric(value) || ~isreal(value) || ~isscalar(value) || ~isfinite(value)
    error('EU2605:BadObjectiveAnchor', ...
        'the injected objective must return a finite real scalar');
end
result = struct( ...
    'coordinates', coordinates, ...
    'value', double(value), ...
    'objective_kind', 'toy_injected');
end
