function population = initialize_ga_population(problem, options)
rng(options.Seed, 'twister');
nvars = problem.nvars;
population = zeros(options.PopulationSize, nvars);

population(1, :) = problem.fixed_genome;
if options.PopulationSize >= 2
    population(2, :) = problem.lb;
end
if options.PopulationSize >= 3
    population(3, :) = problem.ub;
end

for i = 4:options.PopulationSize
    x = problem.fixed_genome;
    for j = 1:nvars
        if problem.case.optimize_mask(j)
            x(j) = randi([problem.lb(j), problem.ub(j)]);
        end
    end
    population(i, :) = apply_case_mask(x, problem);
end

for i = 1:options.PopulationSize
    population(i, :) = apply_case_mask(population(i, :), problem);
end
end
