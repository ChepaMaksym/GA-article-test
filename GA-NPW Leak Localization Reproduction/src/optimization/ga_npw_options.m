function options = ga_npw_options(seed)
if nargin < 1 || isempty(seed)
    seed = 20260428;
end

article = article_reported();
options = struct();
options.PopulationSize = article.ga.population_size;
options.MaxGenerations = article.ga.iterations;
options.CrossoverRate = article.ga.crossover_rate;
options.MutationRate = article.ga.mutation_rate;
options.Selection = article.ga.selection;
options.TournamentSize = 3;
options.Seed = seed;
options.MutationScale = [0.08, 0.04, 0.05, 0.08];
end
