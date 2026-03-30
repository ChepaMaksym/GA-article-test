function run_full_replication()

clc; clear; close all;

T = 3;
J = 5;
N = 6;

Smax = 2.5;
Qmax = 100;
Hmin = 300;
Hmax = 1000;
Hsource = 300;

% Use one run by default for fast iteration.
% Set nRuns = 50 if you want the same repeated-study setup as the paper.
nRuns = 1;

lbS = zeros(J,T);
ubS = Smax * ones(J,T);

lbQ = zeros(J,T);
ubQ = Qmax * ones(J,T);

lbH = Hmin * ones(N,T);
ubH = Hmax * ones(N,T);
lbH(1,:) = Hsource;
ubH(1,:) = Hsource;

lb = [lbS(:); lbQ(:); lbH(:)]';
ub = [ubS(:); ubQ(:); ubH(:)]';
nVar = numel(lb);

options = optimoptions('gamultiobj', ...
    'PopulationSize', 315, ...
    'MaxGenerations', 100, ...
    'CrossoverFraction', 0.8, ...
    'MutationFcn', {@mutationgaussian, 1, 1}, ...
    'Display', 'iter');

results = [];
solutions = [];

for k = 1:nRuns
    fprintf('Run %d/%d\n', k, nRuns);

    [x, fval] = gamultiobj(@objective_full, nVar, [], [], [], [], ...
        lb, ub, @constraints_full, options);

    results = [results; fval]; %#ok<AGROW>
    solutions = [solutions; x]; %#ok<AGROW>
end

if isempty(results)
    error('GA returned no feasible solutions.');
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
    S = reshape(solutions(i,1:J*T), [J,T]);
    B = double(S >= 0.2);

    fprintf('Solution %d | Cost = %.2f $ | Switching = %.0f\n', ...
        i, results(i,1), results(i,2));
    disp('Speed ratios:');
    disp(S);
    disp('Pump states:');
    disp(B);
end

end
