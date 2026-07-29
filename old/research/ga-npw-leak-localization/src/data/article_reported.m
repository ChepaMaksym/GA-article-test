function article = article_reported()
article = struct();
article.data_type = 'article_reported';
article.title = 'Genetic algorithm optimization of negative pressure wave method for robust real time leak detection in long distance pipelines';
article.authors = {'Ali Sharifi', 'Seyyed Faramarz Ranjbar', 'Seyed Amirreza Mousavi Alamdardehi', 'Naser Aslani', 'Reza Zarezadeh', 'Hamid Majidi', 'Fatemeh Asadi'};
article.journal = 'Scientific Reports';
article.volume = 15;
article.article_number = 36429;
article.year = 2025;
article.published = '17 October 2025';
article.doi = '10.1038/s41598-025-20525-5';
article.url = 'https://www.nature.com/articles/s41598-025-20525-5';

article.pipeline_length_m = 175000;
article.pipeline_length_km = 175;
article.pipeline_diameter_in = 22;
article.controlled_leak_tests = 10;
article.sampling_rate_Hz = 200;

article.ga.population_size = 80;
article.ga.iterations = 200;
article.ga.crossover_rate = 0.3;
article.ga.mutation_rate = 0.05;
article.ga.selection = 'tournament';

article.reported_results.npw_mean_error_percent = 11;
article.reported_results.hgi_mean_error_percent = 18;
article.reported_results.ga_npw_mean_error_percent = 5;
article.reported_results.ga_npw_detection_delay_s = 10;
article.reported_results.traditional_detection_delay_s = [30, 40];
article.reported_results.ga_npw_computation_time_ms_upper = 350;

article.robustness.wave_speed_deviation_percent = [-10, 10];
article.robustness.flow_rate_percent_of_nominal = [60, 120];
article.robustness.max_sync_error_s = 2;
article.robustness.pipeline_length_scaling_km = [50, 300];

article.note = ['These fields capture values reported in the article. They are not generated ' ...
    'by the synthetic reproduction sandbox.'];
end
