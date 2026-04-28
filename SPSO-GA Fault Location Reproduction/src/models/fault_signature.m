function signature = fault_signature(network, faultSection, sensorNodes)
if nargin < 3 || isempty(sensorNodes)
    sensorNodes = network.sensor_nodes;
end
if faultSection < 1 || faultSection > network.section_count
    error('Fault section must be between 1 and %d.', network.section_count);
end

childNode = network.branches(faultSection, 2);
faultDownstream = downstream_nodes(network, childNode);
signature = ismember(sensorNodes(:), faultDownstream);
signature = double(signature(:)');
end
