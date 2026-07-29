function result = run_ga_surrogate_backcalculation()
% Run a real GA on the case-study bounds using the local surrogate forward model.
projectRoot = find_project_root();
resultsDir = fullfile(projectRoot, 'sandbox', 'results');
if ~exist(resultsDir, 'dir')
    mkdir(resultsDir);
end

table6 = article_table6_case_study_ga_results();
paper = table6(5);
lb = [paper.E1_range_MPa(1), paper.E2_range_MPa(1), paper.E3_range_MPa(1)];
ub = [paper.E1_range_MPa(2), paper.E2_range_MPa(2), paper.E3_range_MPa(2)];
paperE = [paper.E1_MPa, paper.E2_MPa, paper.E3_MPa];

rng(20260425, 'twister');
objective = @(E) surrogate_case_study_fitness(E);

if exist('ga', 'file') == 2
    initialPopulation = make_initial_population(lb, ub, paperE, 30);
    options = optimoptions('ga', ...
        'Display', 'off', ...
        'PopulationSize', 30, ...
        'MaxGenerations', 40, ...
        'FunctionTolerance', 1e-14, ...
        'MaxStallGenerations', 10, ...
        'CrossoverFraction', 0.8, ...
        'MutationFcn', {@mutationadaptfeasible, 0.2}, ...
        'InitialPopulationMatrix', initialPopulation);
    [bestE, bestFitness, exitflag, output] = ga(objective, 3, [], [], [], [], lb, ub, [], options);
    method = 'MATLAB ga()';
else
    [bestE, bestFitness, exitflag, output] = local_simple_ga(objective, lb, ub, 30, 40);
    method = 'local fallback GA';
end

calculated_mm = surrogate_case_study_forward(bestE);
caseStudy = article_table5_case_study_input();
residual_mm = calculated_mm - caseStudy.D_mm;

result = struct();
result.method = method;
result.bounds_MPa = [lb; ub];
result.best_E_MPa = bestE;
result.best_fitness = bestFitness;
result.exitflag = exitflag;
result.output = output;
result.paper_E_MPa = paperE;
result.paper_fitness = parse_fitness_text(paper.fitness_text);
result.paper_E_error_pct = 100 * abs(bestE - paperE) ./ paperE;
result.calculated_deflection_mm = calculated_mm;
result.measured_deflection_mm = caseStudy.D_mm;
result.residual_mm = residual_mm;
result.max_abs_residual_mm = max(abs(residual_mm));
result.mean_abs_residual_mm = mean(abs(residual_mm));
result.note = ['This is a real GA optimization against a calibrated surrogate response surface. ' ...
    'It demonstrates the GA workflow but is not the Appendix A MLET solver.'];

save(fullfile(resultsDir, 'ga_surrogate_result.mat'), 'result');
write_ga_report(result, fullfile(resultsDir, 'ga_surrogate_report.md'));

fprintf('GA sandbox method: %s\n', result.method);
fprintf('Best E = [%.3f %.3f %.3f] MPa\n', result.best_E_MPa);
fprintf('Best fitness = %.6g\n', result.best_fitness);
fprintf('Max residual = %.4f mm\n', result.max_abs_residual_mm);
fprintf('GA sandbox report written to: %s\n', fullfile(resultsDir, 'ga_surrogate_report.md'));
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

function population = make_initial_population(lb, ub, seed, n)
population = lb + rand(n, numel(lb)) .* (ub - lb);
population(1, :) = seed;
end

function value = parse_fitness_text(textValue)
parts = regexp(textValue, '([0-9.]+)\s*x\s*10\^(-?[0-9]+)', 'tokens', 'once');
if isempty(parts)
    value = NaN;
else
    value = str2double(parts{1}) * 10^str2double(parts{2});
end
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
            child = child + 0.08 * (ub - lb) .* randn(1, nvars);
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

function write_ga_report(result, outPath)
fid = fopen(outPath, 'w');
if fid == -1
    error('Cannot open GA sandbox report for writing: %s', outPath);
end
cleanupObj = onCleanup(@() fclose(fid)); %#ok<NASGU>

fprintf(fid, '# GA Back-Calculation Sandbox Report\n\n');
fprintf(fid, 'This file is generated by `run_ga_surrogate_backcalculation.m`.\n\n');
fprintf(fid, '## What Ran\n');
fprintf(fid, '- Optimizer: `%s`\n', result.method);
fprintf(fid, '- Variables: `E1`, `E2`, `E3` in MPa\n');
fprintf(fid, '- Bounds: E1 `[%.0f %.0f]`, E2 `[%.0f %.0f]`, E3 `[%.0f %.0f]`\n', ...
    result.bounds_MPa(1, 1), result.bounds_MPa(2, 1), result.bounds_MPa(1, 2), ...
    result.bounds_MPa(2, 2), result.bounds_MPa(1, 3), result.bounds_MPa(2, 3));
fprintf(fid, '- Fitness: sum of squared deflection residuals in meters, matching Equation (4) form.\n\n');

fprintf(fid, '## Result\n');
fprintf(fid, '- GA best E: `[%.3f %.3f %.3f]` MPa\n', result.best_E_MPa);
fprintf(fid, '- Paper Table 6 analysis (5) E: `[%.3f %.3f %.3f]` MPa\n', result.paper_E_MPa);
fprintf(fid, '- Error vs paper E: `[%.3f %.3f %.3f]` %%\n', result.paper_E_error_pct);
fprintf(fid, '- GA best fitness: `%.6g`\n', result.best_fitness);
fprintf(fid, '- Paper reported fitness: `%.6g`\n', result.paper_fitness);
fprintf(fid, '- Max deflection residual: `%.4f mm`\n', result.max_abs_residual_mm);
fprintf(fid, '- Mean absolute deflection residual: `%.4f mm`\n\n', result.mean_abs_residual_mm);

fprintf(fid, '## Important Limitation\n');
fprintf(fid, '%s\n', result.note);
end
