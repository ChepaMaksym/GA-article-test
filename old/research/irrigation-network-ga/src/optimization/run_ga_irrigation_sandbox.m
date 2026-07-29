function result = run_ga_irrigation_sandbox()
projectRoot = find_project_root();
resultsDir = fullfile(projectRoot, 'sandbox', 'results');
if ~exist(resultsDir, 'dir')
    mkdir(resultsDir);
end

basic = article_basic_information();
prices = article_table3_pipe_prices();
rng(20260425, 'twister');

nvars = 15;
lb = [ones(1, 10), 41 * ones(1, 5)];
ub = [numel(prices.outside_diameter_mm) * ones(1, 10), 50 * ones(1, 5)];
objective = @(x) irrigation_surrogate_objective(x);
initial = initial_population(80, lb, ub);

if exist('ga', 'file') == 2
    options = optimoptions('ga', ...
        'Display', 'off', ...
        'PopulationSize', 80, ...
        'MaxGenerations', basic.ga_iterations, ...
        'CrossoverFraction', basic.crossover_probability, ...
        'MutationFcn', {@mutationadaptfeasible, basic.mutation_probability}, ...
        'InitialPopulationMatrix', initial);
    [bestX, bestObjective, exitflag, output] = ga(objective, nvars, [], [], [], [], lb, ub, [], options);
    method = 'MATLAB ga()';
else
    [bestX, bestObjective, exitflag, output] = local_simple_ga(objective, lb, ub, 80, basic.ga_iterations);
    method = 'local fallback GA';
end

[~, details] = irrigation_surrogate_objective(bestX);
reportedDesigns = evaluate_reported_designs();

result = struct();
result.method = method;
result.model = 'SOM surrogate';
result.best_x = bestX;
result.best_objective = bestObjective;
result.best_branch_diameter_mm = details.branch_diameter_mm;
result.best_frequency_Hz = details.frequency_Hz;
result.network_cost = details.network_cost;
result.energy_cost = details.energy_cost;
result.penalty = details.penalty;
result.exitflag = exitflag;
result.output = output;
result.reported_designs = reportedDesigns;
result.note = ['This is an executable GA sandbox over simplified branch-level diameters and frequencies. ' ...
    'It is not a full hydraulic reproduction because the source XML does not include the full Figure 5 network geometry or original solver code.'];
result.report_path = fullfile(resultsDir, 'ga_sandbox_report.md');

save(fullfile(resultsDir, 'ga_sandbox_result.mat'), 'result');
write_ga_sandbox_report(result);

fprintf('GA irrigation sandbox method: %s\n', result.method);
fprintf('Best surrogate objective: %.6f\n', result.best_objective);
fprintf('Best branch diameters: [%s] mm\n', strjoin(compose('%.0f', result.best_branch_diameter_mm), ', '));
fprintf('Best frequencies: [%s] Hz\n', strjoin(compose('%.0f', result.best_frequency_Hz), ', '));
fprintf('GA sandbox report written to: %s\n', result.report_path);
end

function population = initial_population(n, lb, ub)
population = lb + rand(n, numel(lb)) .* (ub - lb);
table6 = article_table6_optimized_diameters();
population(1, :) = encode_seed(table6.PDM, 50 * ones(1, 5));
population(2, :) = encode_seed(table6.SOM, [50 48 43 48 43]);
end

function seed = encode_seed(diameterMatrix, frequency)
prices = article_table3_pipe_prices();
branchDiameter = zeros(1, size(diameterMatrix, 1));
for row = 1:size(diameterMatrix, 1)
    values = diameterMatrix(row, :);
    values = values(~isnan(values) & ismember(values, prices.outside_diameter_mm));
    branchDiameter(row) = mode(values);
end
idx = zeros(size(branchDiameter));
for i = 1:numel(branchDiameter)
    idx(i) = find(prices.outside_diameter_mm == branchDiameter(i), 1);
end
seed = [idx, frequency];
end

function [bestX, bestF, exitflag, output] = local_simple_ga(objective, lb, ub, populationSize, maxGenerations)
nvars = numel(lb);
population = lb + rand(populationSize, nvars) .* (ub - lb);
fitness = evaluate_population(objective, population);

for generation = 1:maxGenerations
    [fitness, order] = sort(fitness);
    population = population(order, :);
    eliteCount = max(2, round(0.1 * populationSize));
    nextPopulation = population(1:eliteCount, :);
    while size(nextPopulation, 1) < populationSize
        p1 = tournament(population, fitness);
        p2 = tournament(population, fitness);
        alpha = rand(1, nvars);
        child = alpha .* p1 + (1 - alpha) .* p2;
        if rand < 0.2
            child = child + 0.12 * (ub - lb) .* randn(1, nvars);
        end
        child = min(max(child, lb), ub);
        nextPopulation(end + 1, :) = child; %#ok<AGROW>
    end
    population = nextPopulation;
    fitness = evaluate_population(objective, population);
end

[bestF, idx] = min(fitness);
bestX = population(idx, :);
exitflag = 1;
output = struct('generations', maxGenerations, 'message', 'Local fallback GA completed.');
end

function fitness = evaluate_population(objective, population)
fitness = zeros(size(population, 1), 1);
for i = 1:size(population, 1)
    fitness(i) = objective(population(i, :));
end
end

function parent = tournament(population, fitness)
idx = randi(size(population, 1), [3, 1]);
[~, bestLocal] = min(fitness(idx));
parent = population(idx(bestLocal), :);
end

function write_ga_sandbox_report(result)
fid = fopen(result.report_path, 'w');
if fid == -1
    error('Cannot open GA report for writing: %s', result.report_path);
end
cleanupObj = onCleanup(@() fclose(fid)); %#ok<NASGU>

fprintf(fid, '# GA Irrigation Sandbox Report\n\n');
fprintf(fid, 'Generated by `run_ga_irrigation_sandbox.m`.\n\n');
fprintf(fid, '## Run Settings\n');
fprintf(fid, '- Optimizer: `%s`\n', result.method);
fprintf(fid, '- Variables: 10 branch-level pipe diameters and 5 sector frequencies.\n');
fprintf(fid, '- Objective: surrogate annualized network cost + surrogate energy cost + soft penalties.\n\n');

fprintf(fid, '## Best Candidate\n');
fprintf(fid, '- Branch diameters: `[%s]` mm\n', strjoin(compose('%.0f', result.best_branch_diameter_mm), ' '));
fprintf(fid, '- Frequencies: `[%s]` Hz\n', strjoin(compose('%.0f', result.best_frequency_Hz), ' '));
fprintf(fid, '- Objective: `%.6f`\n', result.best_objective);
fprintf(fid, '- Network cost component: `%.6f`\n', result.network_cost);
fprintf(fid, '- Energy cost component: `%.6f`\n', result.energy_cost);
fprintf(fid, '- Penalty: `%.6f`\n\n', result.penalty);

fprintf(fid, '## Reported Designs In Same Surrogate\n');
for i = 1:numel(result.reported_designs)
    row = result.reported_designs(i);
    fprintf(fid, '- `%s`: objective `%.6f`, network `%.6f`, energy `%.6f`, penalty `%.6f`\n', ...
        row.model, row.objective, row.network_cost, row.energy_cost, row.penalty);
end
fprintf(fid, '\n## Limitation\n%s\n', result.note);
end

function projectRoot = find_project_root()
currentDir = fileparts(mfilename('fullpath'));
projectRoot = currentDir;
while ~isfile(fullfile(projectRoot, 'main.m'))
    parentDir = fileparts(projectRoot);
    if strcmp(parentDir, projectRoot)
        error('Project root with main.m was not found.');
    end
    projectRoot = parentDir;
end
end
