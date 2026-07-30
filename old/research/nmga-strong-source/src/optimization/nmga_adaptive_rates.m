function [crossoverRate, mutationRate] = nmga_adaptive_rates(generation, maxGenerations, options)
progress = min(max(generation ./ max(maxGenerations, 1), 0), 1);
crossoverRate = options.NMGACrossoverInitial .* (1 - progress) .^ options.NMGAScheduleExponent;
mutationRate = options.NMGAMutationInitial .* (1 + progress) .^ options.NMGAScheduleExponent;
crossoverRate = min(max(crossoverRate, options.NMGACrossoverMin), options.NMGACrossoverMax);
mutationRate = min(max(mutationRate, options.NMGAMutationMin), options.NMGAMutationMax);
end
