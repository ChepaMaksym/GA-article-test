function run_full_replication()

clc; clear; close all;

T = 3;
J = 5;

Smax = 2.5;
Qmax = 100;
Con = 60;
nRuns = 50;

check_basic_feasibility(T, J, Qmax, Con, Smax);

lbB = zeros(J,T);
ubB = ones(J,T);

lbS = zeros(J,T);
ubS = Smax * ones(J,T);

lbQ = zeros(J,T);
ubQ = Qmax * ones(J,T);

lb = [lbB(:); lbS(:); lbQ(:)]';
ub = [ubB(:); ubS(:); ubQ(:)]';
nVar = numel(lb);
intcon = 1:(J*T);

options = optimoptions('gamultiobj', ...
    'PopulationSize', 1200, ...
    'MaxGenerations', 100, ...
    'CrossoverFraction', 0.8, ...
    'MutationFcn', {@mutationgaussian, 0.4, 0.2}, ...
    'ConstraintTolerance', 1e-4, ...
    'Display', 'iter');

results = [];
solutions = [];
constraintViolations = [];

for k = 1:nRuns
    fprintf('Run %d/%d\n', k, nRuns);

    [x, fval] = gamultiobj(@objective_full, nVar, [], [], [], [], ...
        lb, ub, @constraints_full, intcon, options);

    feasibleMask = false(size(x,1),1);
    runViolation = inf(size(x,1),1);

    for i = 1:size(x,1)
        [c, ceq] = constraints_full(x(i,:));
        maxIneq = max([c(:); -inf]);
        maxEq = max(abs([ceq(:); 0]));
        runViolation(i) = max(maxIneq, maxEq);
        feasibleMask(i) = all(c <= options.ConstraintTolerance) && ...
            all(abs(ceq) <= options.ConstraintTolerance);
    end

    fprintf('  feasible solutions: %d / %d | best violation: %.3e\n', ...
        nnz(feasibleMask), size(x,1), min(runViolation));

    results = [results; fval(feasibleMask,:)]; %#ok<AGROW>
    solutions = [solutions; x(feasibleMask,:)]; %#ok<AGROW>
    constraintViolations = [constraintViolations; runViolation(feasibleMask)]; %#ok<AGROW>
end

if isempty(results)
    error('GA returned no feasible solutions. The model still needs tighter physical calibration.');
end

[results, keepIdx] = unique(round(results, 6), 'rows', 'stable');
solutions = solutions(keepIdx,:);
[results, sortIdx] = sortrows(results, [2 1]);
solutions = solutions(sortIdx,:);

figure;
scatter(results(:,2), results(:,1), 48, 'filled');
xlabel('Pump Switching');
ylabel('Energy Cost [$]');
title('Pareto Front');
grid on;

fprintf('\nPareto solutions\n');
fprintf('----------------\n');

for i = 1:size(results,1)
    B = reshape(solutions(i,1:J*T), [J,T]);
    S = reshape(solutions(i,J*T+1:2*J*T), [J,T]);

    fprintf('Solution %d | Cost = %.2f $ | Switching = %.0f\n', ...
        i, results(i,1), results(i,2));
    disp('Speed ratios:');
    disp(S);
    disp('Pump states:');
    disp(B);
end

end

function check_basic_feasibility(T, J, Qmax, Con, Smax)

if J ~= 5
    warning('The quick feasibility screen assumes the 5-pump reference topology.');
end

branchCapacity = T * Qmax;
upstreamCapacity = T * Qmax;

if branchCapacity < Con
    error(['Delivery target is impossible from variable bounds alone: ', ...
        'T*Qmax = %.2f < Con = %.2f.'], branchCapacity, Con);
end

if upstreamCapacity < 2 * Con
    error(['The upstream line cannot supply both sinks within bounds: ', ...
        'T*Qmax = %.2f < 2*Con = %.2f.'], upstreamCapacity, 2 * Con);
end

if Smax <= 0
    error('Smax must be positive.');
end

fprintf(['Basic feasibility screen passed | branch capacity per sink = %.2f ', ...
    '| required delivery per sink = %.2f\n'], branchCapacity, Con);

end
