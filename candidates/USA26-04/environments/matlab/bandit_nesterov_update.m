function result = bandit_nesterov_update(value, momentum, reward, learning_rate, momentum_factor)
%BANDIT_NESTEROV_UPDATE Port the article's local gradient/momentum equations.

inputs = [value, momentum, reward, learning_rate, momentum_factor];
if ~isnumeric(inputs) || ~isreal(inputs) || numel(inputs) ~= 5 ...
        || any(~isfinite(inputs))
    error('banditverify:InvalidUpdateInput', 'Update inputs must be finite scalars.');
end
if learning_rate <= 0
    error('banditverify:InvalidLearningRate', 'Learning rate must be positive.');
end
if momentum_factor < 0 || momentum_factor >= 1
    error('banditverify:InvalidMomentumFactor', ...
        'Momentum factor must be in [0,1).');
end
result.gradient = 2 * (value - reward);
result.momentum = momentum_factor * momentum + result.gradient;
result.value = value - learning_rate ...
    * (result.gradient + momentum_factor * result.momentum);
if any(~isfinite([result.gradient, result.momentum, result.value]))
    error('banditverify:NonFiniteUpdate', ...
        'Controller update produced a non-finite value.');
end
end
