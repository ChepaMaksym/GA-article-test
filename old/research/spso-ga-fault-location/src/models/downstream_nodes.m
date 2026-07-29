function nodes = downstream_nodes(network, startNode)
children = cell(network.node_count, 1);
for i = 1:size(network.branches, 1)
    parent = network.branches(i, 1);
    child = network.branches(i, 2);
    children{parent}(end + 1) = child; %#ok<AGROW>
end

nodes = [];
stack = startNode;
while ~isempty(stack)
    node = stack(end);
    stack(end) = [];
    nodes(end + 1) = node; %#ok<AGROW>
    stack = [stack, children{node}]; %#ok<AGROW>
end
nodes = unique(nodes);
end
