function net = decode_mlp_weights(weights, inputCount, hiddenNodes)
weights = weights(:)';
offset = 0;
net.W1 = reshape(weights(offset + (1:inputCount * hiddenNodes)), inputCount, hiddenNodes);
offset = offset + inputCount * hiddenNodes;
net.b1 = reshape(weights(offset + (1:hiddenNodes)), 1, hiddenNodes);
offset = offset + hiddenNodes;
net.W2 = reshape(weights(offset + (1:hiddenNodes)), hiddenNodes, 1);
offset = offset + hiddenNodes;
net.b2 = weights(offset + 1);
end
