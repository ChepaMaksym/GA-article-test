function article = article_reported()
article = struct();
article.data_type = 'article_reported';
article.title = 'Faults locating of power distribution systems based on successive PSO-GA algorithm';
article.journal = 'Scientific Reports';
article.year = 2024;
article.doi = '10.1038/s41598-024-61306-w';
article.url = 'https://www.nature.com/articles/s41598-024-61306-w';

article.network.name = 'IEEE33-node distribution network';
article.network.node_count = 33;
article.network.section_count = 32;

article.algorithm.population_size = 20;
article.algorithm.iterations = 100;
article.algorithm.repeated_tests = 200;
article.algorithm.pso_ga.omega = 0.9;
article.algorithm.pso_ga.c1 = 3.4;
article.algorithm.pso_ga.c2 = 3.5;
article.algorithm.spso_ga.omega = 0.8;
article.algorithm.spso_ga.c1 = 0.7;
article.algorithm.spso_ga.c2 = 0.1;
article.algorithm.ga_substep.G = 30;
article.algorithm.ga_substep.crossover_probability = 0.9;
article.algorithm.ga_substep.mutation_probability = 0.5;
article.algorithm.reported_difficult_section = 32;
article.algorithm.reported_section32_accuracy_with_N30_percent = 88;

article.note = ['Article-reported settings are encoded for workflow reproduction. Raw FTU ' ...
    'records and exact simulation result tables are not available in this workspace.'];
end
