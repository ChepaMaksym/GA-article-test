function score = mlp_predict(weights, X, hiddenNodes)
if nargin < 3
    hiddenNodes = 2;
end
net = decode_mlp_weights(weights, size(X, 2), hiddenNodes);
hidden = tanh(X * net.W1 + repmat(net.b1, size(X, 1), 1));
score = hidden * net.W2 + net.b2;
end
