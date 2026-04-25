function [c, ceq] = constraints_full(x)

params = local_params();
[B, S, Q] = unpack_variables(x, params);

PH = params.AP * Q.^2 + params.BP * Q .* S + params.CP * S.^2;
PL = params.CL * Q.^2;

H = nodal_heads(PH, PL, params);

c = [];
ceq = [];

% GA handles relaxed inequalities much more reliably than many exact
% nonlinear equalities, so we enforce the hydraulic balances with small
% tolerances instead of strict ceq terms.
c = [c; reshape(abs(Q(1,:) - Q(2,:)) - params.massTol, [], 1)];
c = [c; reshape(abs(Q(2,:) - Q(3,:) - Q(4,:)) - params.massTol, [], 1)];
c = [c; reshape(abs(Q(4,:) - Q(5,:)) - params.massTol, [], 1)];

c(end+1,1) = abs(sum(Q(3,:)) - params.Con) - params.deliveryTol;
c(end+1,1) = abs(sum(Q(5,:)) - params.Con) - params.deliveryTol;

% Explicit article-style coupling between binary pump status, speed, and flow.
c = [c; reshape(S - params.Smax .* B, [], 1)];
c = [c; reshape(params.Smin .* B - S, [], 1)];
c = [c; reshape(Q - params.Qmax .* B, [], 1)];

% Pressure heads must remain inside the admissible operating window.
c = [c; reshape(params.Hmin - H(2:end,:), [], 1)];
c = [c; reshape(H(2:end,:) - params.Hmax, [], 1)];

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

function H = nodal_heads(PH, PL, params)

H = zeros(params.N, params.T);
H(1,:) = params.Hsource;
H(2,:) = H(1,:) + PH(1,:) - PL(1,:);
H(3,:) = H(2,:) + PH(2,:) - PL(2,:);
H(4,:) = H(3,:) + PH(3,:) - PL(3,:);
H(5,:) = H(3,:) + PH(4,:) - PL(4,:);
H(6,:) = H(5,:) + PH(5,:) - PL(5,:);

end

function params = local_params()

params.T = 3;
params.J = 5;
params.N = 6;

params.Smin = 0.2;
params.Smax = 2.5;
params.Qmax = 100;
params.Con = 60;
params.Hsource = 300;
params.Hmin = 300;
params.Hmax = 1000;

params.massTol = 1e-4;
params.deliveryTol = 1e-4;

params.CL = 0.3;
params.AP = 2.3e-6;
params.BP = 8.3;
params.CP = 4.6e-3;

end
