function options = ga_building_options(seed)
if nargin < 1
    seed = 20260503;
end

reported = article_reported();
options = struct();
options.Seed = seed;
options.PopulationSize = reported.ga.population_size;
options.MaxGenerations = reported.ga.generations;
options.CrossoverRate = 0.85;
options.MutationRate = 0.08;
options.MutationStep = 2;
options.TournamentSize = 3;
options.EliteCount = 2;
options.GenotypeType = 'x_only';
end
