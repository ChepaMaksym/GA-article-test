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
spec = article_exact_spec();
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
options.MGAMutationRate = article.algorithm.mga_mutation_rate;
options.NMGACrossoverInitial = article.algorithm.nmga_initial_crossover_rate;
options.NMGAMutationInitial = article.algorithm.nmga_initial_mutation_rate;
options.NMGAScheduleExponent = article.algorithm.nmga_schedule_exponent;
options.NMGACrossoverMax = options.NMGACrossoverInitial;
options.NMGACrossoverMin = 0;
options.NMGAMutationMin = options.NMGAMutationInitial;
options.NMGAMutationMax = options.NMGAMutationInitial * 4;
options.EGPInheritanceRate = 0.3;
options.ObjectiveMode = 'normalized_mse';
options.OperatorMode = 'synthetic_workflow';
options.ArticleExact = false;
options.Bounds = spec.bounds;

switch lower(profile)
    case 'article_exact'
        options.RepeatCount = 100;
        options.MGAGenerations = article.algorithm.mga_generations;
        options.NMGA1000Generations = article.algorithm.nmga_generations(1);
        options.NMGA500Generations = article.algorithm.nmga_generations(2);
        options.ObjectiveMode = spec.objective.mode;
        options.OperatorMode = 'article_exact';
        options.ArticleExact = true;
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
