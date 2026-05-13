function article = article_reported()
spec = article_exact_spec();
article = struct();
article.data_type = 'article_reported';
article.title = spec.source.title;
article.authors = {'Jiming Yao', 'Yajing Liu', 'Zhengwen Feng', 'Tong Liu', 'Shuai Zhou', 'Hongjian Liu'};
article.journal = 'Atmosphere';
article.volume = 14;
article.issue = 1;
article.article_number = 89;
article.year = 2023;
article.published = '31 December 2022';
article.doi = spec.source.doi;
article.url = spec.source.url;

article.scenario = spec.scenario;

article.algorithm.population_size = spec.algorithm.population_size;
article.algorithm.mga_generations = spec.algorithm.mga_generations;
article.algorithm.nmga_generations = spec.algorithm.nmga_generations;
article.algorithm.mga_crossover_rate = spec.algorithm.mga_crossover_rate;
article.algorithm.mga_mutation_rate = spec.algorithm.mga_mutation_rate;
article.algorithm.nmga_initial_crossover_rate = spec.algorithm.nmga_initial_crossover_rate;
article.algorithm.nmga_initial_mutation_rate = spec.algorithm.nmga_initial_mutation_rate;
article.algorithm.nmga_schedule_exponent = spec.algorithm.schedule_exponent;
article.algorithm.beta = spec.algorithm.beta;
article.algorithm.gamma = spec.algorithm.gamma;
article.algorithm.SetMax = spec.algorithm.SetMax;

article.table1 = spec.table1;

article.note = ['Article-reported values are encoded for comparison only. The source page states ' ...
    'data sharing is not applicable, so this project does not claim raw-data reproduction.'];
end
