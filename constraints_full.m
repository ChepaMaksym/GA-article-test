function [c, ceq] = constraints_full(x)

params = local_params();
[S, Q, H] = unpack_variables(x, params);

PH = params.AP * Q.^2 + params.BP * Q .* S + params.CP * S.^2;
PL = params.CL * Q.^2;

c = [];
ceq = [];

% Article-style mass conservation for the 5-segment dendritic network.
ceq = [ceq; reshape(Q(1,:) - Q(2,:), [], 1)];
ceq = [ceq; reshape(Q(2,:) - Q(3,:) - Q(4,:), [], 1)];
ceq = [ceq; reshape(Q(4,:) - Q(5,:), [], 1)];

% Momentum balance using nodal heads and the pump head curve.
upstream = [1 2 3 3 5];
downstream = [2 3 4 5 6];

for j = 1:params.J
    for t = 1:params.T
        ceq(end+1,1) = H(downstream(j),t) - H(upstream(j),t) ...
            - PH(j,t) + PL(j,t); %#ok<AGROW>
    end
end

% Delivery contracts on the two delivery branches.
ceq(end+1,1) = sum(Q(3,:)) - params.Con;
ceq(end+1,1) = sum(Q(5,:)) - params.Con;

% Force speed to be either zero or above the minimum admissible ratio.
c = [c; reshape(S .* (params.Smin - S), [], 1)];

% No flow is allowed through a pump that is effectively off.
c = [c; reshape(Q .* (params.Smin - S), [], 1)];

end

function [S, Q, H] = unpack_variables(x, params)

idx = 1;
nJS = params.J * params.T;
nQS = params.J * params.T;
nHS = params.N * params.T;

S = reshape(x(idx:idx+nJS-1), [params.J, params.T]);
idx = idx + nJS;

Q = reshape(x(idx:idx+nQS-1), [params.J, params.T]);
idx = idx + nQS;

H = reshape(x(idx:idx+nHS-1), [params.N, params.T]);

end

function params = local_params()

params.T = 3;
params.J = 5;
params.N = 6;

params.Smin = 0.2;
params.Con = 60;

params.CL = 0.3;
params.AP = 2.3e-6;
params.BP = 8.3;
params.CP = 4.6e-3;

end
