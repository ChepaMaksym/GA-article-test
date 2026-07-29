function observation = build_fault_observation(caseData)
network = ieee33_synthetic_network();
sensorNodes = select_sensor_nodes(network, caseData.sensor_mode);
cleanSignature = fault_signature(network, caseData.true_fault_section, sensorNodes);
observedSignature = cleanSignature;
flipIdx = deterministic_flip_indices(numel(observedSignature), caseData.true_fault_section, caseData.flip_count);
observedSignature(flipIdx) = 1 - observedSignature(flipIdx);

observation = struct();
observation.data_type = caseData.data_type;
observation.name = caseData.name;
observation.network = network;
observation.sensor_nodes = sensorNodes;
observation.true_fault_section = caseData.true_fault_section;
observation.clean_signature = cleanSignature;
observation.observed_signature = observedSignature;
observation.flip_count = caseData.flip_count;
observation.sensor_mode = caseData.sensor_mode;
observation.weight = caseData.weight;
observation.note = caseData.note;
end

function sensorNodes = select_sensor_nodes(network, mode)
switch lower(mode)
    case 'full'
        sensorNodes = network.sensor_nodes;
    case 'missing_every_third'
        sensorNodes = network.sensor_nodes(mod(network.sensor_nodes, 3) ~= 0);
    case 'sparse_terminal'
        sensorNodes = [6, 12, 18, 22, 25, 29, 33];
    otherwise
        error('Unknown sensor mode: %s', mode);
end
end

function idx = deterministic_flip_indices(n, faultSection, flipCount)
if flipCount <= 0
    idx = [];
    return;
end
seed = mod((faultSection * [7, 13, 19, 23]) - 1, n) + 1;
idx = unique(seed, 'stable');
while numel(idx) < flipCount
    idx(end + 1) = mod(idx(end) + 5 - 1, n) + 1; %#ok<AGROW>
    idx = unique(idx, 'stable');
end
idx = idx(1:flipCount);
end
