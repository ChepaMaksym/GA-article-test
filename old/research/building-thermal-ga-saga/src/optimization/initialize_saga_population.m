function population = initialize_saga_population(problem, options)
xPopulation = initialize_ga_population(problem, options);
population = repmat(empty_saga_individual(problem.nvars), options.PopulationSize, 1);

for i = 1:options.PopulationSize
    population(i).x = xPopulation(i, :);
    if i == 1
        population(i).theta = options.InitialTheta;
    else
        population(i).theta = random_theta(options);
    end
    population(i).fitness = [];
end
end

function individual = empty_saga_individual(nvars)
individual = struct();
individual.x = zeros(1, nvars);
individual.theta = struct('Pm', 0, 'Pc', 0, 'sigma', 0);
individual.fitness = [];
end

function theta = random_theta(options)
theta = struct();
theta.Pm = rand_uniform(options.ThetaBounds.Pm);
theta.Pc = rand_uniform(options.ThetaBounds.Pc);
theta.sigma = rand_uniform(options.ThetaBounds.sigma);
end

function value = rand_uniform(bounds)
value = bounds(1) + rand * (bounds(2) - bounds(1));
end
