function [sigmaY_m, sigmaZ_m] = pasquill_gifford_e(distance_m)
distance_m = max(distance_m, 1.0e-6);

% Rural Pasquill-Gifford class E approximation.
sigmaY_m = 0.06 .* distance_m ./ sqrt(1 + 0.0001 .* distance_m);
sigmaZ_m = 0.03 .* distance_m ./ (1 + 0.0003 .* distance_m);
sigmaY_m = max(sigmaY_m, 1.0e-6);
sigmaZ_m = max(sigmaZ_m, 1.0e-6);
end
