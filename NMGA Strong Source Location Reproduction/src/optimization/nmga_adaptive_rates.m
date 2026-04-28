function [crossoverRate, mutationRate] = nmga_adaptive_rates(generation, maxGenerations, options)
progress = min(max(generation ./ max(maxGenerations, 1), 0), 1);
crossoverRate = options.NMGACrossoverMax ...
    - (options.NMGACrossoverMax - options.NMGACrossoverMin) .* progress .^ options.Beta;
mutationRate = options.NMGAMutationMin ...
    + (options.NMGAMutationMax - options.NMGAMutationMin) .* progress .^ options.Gamma;
end
