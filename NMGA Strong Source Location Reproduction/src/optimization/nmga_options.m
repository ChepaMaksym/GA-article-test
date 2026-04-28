function options = nmga_options(method, profile, seed)
if nargin < 1 || isempty(method)
    method = 'NMGA';
end
if nargin < 2 || isempty(profile)
    profile = 'quick';
end
if nargin < 3 || isempty(seed)
    seed = 20260428;
end

article = article_reported();
options = struct();
options.Method = upper(method);
options.Profile = lower(profile);
options.Seed = seed;
options.PopulationSize = article.algorithm.population_size;
options.Beta = article.algorithm.beta;
options.Gamma = article.algorithm.gamma;
options.SetMax = article.algorithm.SetMax;
options.TournamentSize = 3;
options.MGACrossoverRate = article.algorithm.mga_crossover_rate;
options.MGAMutationRate = 0.04;
options.NMGACrossoverMax = 0.85;
options.NMGACrossoverMin = 0.25;
options.NMGAMutationMin = 0.01;
options.NMGAMutationMax = 0.18;

switch lower(profile)
    case 'full'
        options.RepeatCount = 100;
        options.MGAGenerations = article.algorithm.mga_generations;
        options.NMGA1000Generations = article.algorithm.nmga_generations(1);
        options.NMGA500Generations = article.algorithm.nmga_generations(2);
    case 'quick'
        options.RepeatCount = 5;
        options.MGAGenerations = 220;
        options.NMGA1000Generations = 160;
        options.NMGA500Generations = 100;
    case 'unit'
        options.RepeatCount = 1;
        options.PopulationSize = 40;
        options.MGAGenerations = 45;
        options.NMGA1000Generations = 45;
        options.NMGA500Generations = 45;
    otherwise
        error('Unknown NMGA profile: %s', profile);
end
end
