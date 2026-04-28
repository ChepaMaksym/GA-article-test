function options = spso_ga_options(method, seed)
if nargin < 1 || isempty(method)
    method = 'SPSO-GA';
end
if nargin < 2 || isempty(seed)
    seed = 20260428;
end

article = article_reported();
options = struct();
options.Method = upper(method);
options.Seed = seed;
options.PopulationSize = article.algorithm.population_size;
options.Iterations = article.algorithm.iterations;
options.GASubstepGenerations = article.algorithm.ga_substep.G;
options.CrossoverProbability = article.algorithm.ga_substep.crossover_probability;
options.MutationProbability = article.algorithm.ga_substep.mutation_probability;
options.MutationScale = 0.15;

if strcmpi(method, 'PSO-GA')
    options.Omega = article.algorithm.pso_ga.omega;
    options.C1 = article.algorithm.pso_ga.c1;
    options.C2 = article.algorithm.pso_ga.c2;
else
    options.Omega = article.algorithm.spso_ga.omega;
    options.C1 = article.algorithm.spso_ga.c1;
    options.C2 = article.algorithm.spso_ga.c2;
end
end
