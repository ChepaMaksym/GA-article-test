function n = mlp_weight_count(inputCount, hiddenNodes)
n = inputCount * hiddenNodes + hiddenNodes + hiddenNodes + 1;
end
