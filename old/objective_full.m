function f = objective_full(x)

params = local_params();
[B, S, Q] = unpack_variables(x, params);

B = min(max(round(B), 0), 1);
S = S .* B;
Q = Q .* B;

P = params.a * Q.^3 + ...
    params.b * (Q.^2) .* S + ...
    params.c * Q .* (S.^2) + ...
    params.d * S.^3;

P = max(P, 0);
P(S < params.Smin) = 0;

energy = params.dt * sum(sum(P .* params.tariffMatrix));
deliveryPenalty = abs(sum(Q(3,:)) - params.Con) + ...
    abs(sum(Q(5,:)) - params.Con);

energy = energy + params.lambdaDelivery * deliveryPenalty;

if sum(Q(:)) < params.zeroFlowThreshold
    energy = max(energy, params.degeneratePenalty);
end

switching = sum(sum(abs(diff(B, 1, 2))));

f = [energy, switching];

end

function [B, S, Q] = unpack_variables(x, params)

idx = 1;
nBS = params.J * params.T;
nJS = params.J * params.T;
nQS = params.J * params.T;

B = reshape(x(idx:idx+nBS-1), [params.J, params.T]);
idx = idx + nBS;

S = reshape(x(idx:idx+nJS-1), [params.J, params.T]);
idx = idx + nJS;

Q = reshape(x(idx:idx+nQS-1), [params.J, params.T]);

end

function params = local_params()

params.T = 3;
params.J = 5;

params.Smin = 0.2;
params.dt = 8;
params.Con = 60;

params.lambdaDelivery = 1e3;
params.zeroFlowThreshold = 1e-3;
params.degeneratePenalty = 1e6;

params.a = 7.4e-3;
params.b = 1.66;
params.c = 5.7e-7;
params.d = 3.6e-3;

params.tariff = [0.08 0.06 0.09];
params.tariffMatrix = repmat(params.tariff, params.J, 1);

end
