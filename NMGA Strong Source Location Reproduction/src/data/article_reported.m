function article = article_reported()
article = struct();
article.data_type = 'article_reported';
article.title = 'Application of New Modified Genetic Algorithm in Inverse Calculation of Strong Source Location';
article.authors = {'Jiming Yao', 'Yajing Liu', 'Zhengwen Feng', 'Tong Liu', 'Shuai Zhou', 'Hongjian Liu'};
article.journal = 'Atmosphere';
article.volume = 14;
article.issue = 1;
article.article_number = 89;
article.year = 2023;
article.published = '4 January 2023';
article.doi = '10.3390/atmos14010089';
article.url = 'https://www.mdpi.com/2073-4433/14/1/89';

article.scenario.Q_gps = 15178.32;
article.scenario.Hr_m = 2;
article.scenario.wind_speed_mps = 2.0;
article.scenario.stability = 'E';
article.scenario.target_x_m = -25;
article.scenario.target_y_m = 16;

article.algorithm.population_size = 100;
article.algorithm.mga_generations = 2000;
article.algorithm.nmga_generations = [1000, 500];
article.algorithm.mga_crossover_rate = 0.6;
article.algorithm.beta = 0.7;
article.algorithm.gamma = 0.5;
article.algorithm.SetMax = 20;

article.table1 = [ ...
    table_row('MGA', '100 x 2000', 49.86, 0.1148, 0.0604, 25.02, 0.0139, 0.0018, 10442.96, 402.8120, 143.0570, NaN, NaN, NaN); ...
    table_row('NMGA', '100 x 1000', -25.0000, 0.0000, 0.0000, 16.0000, 0.0000, 0.0000, 15178.00, 0.0000, 0.0000, 2.0000, 0.0000, 0.0000); ...
    table_row('NMGA', '100 x 500', -24.9719, 0.0278, 0.0115, 16.0081, 0.0081, 0.0035, 15173.00, 6.8047, 2.8247, 1.9981, 0.0007, 0.0002)];

article.note = ['Article-reported values are encoded for comparison only. The source page states ' ...
    'data sharing is not applicable, so this project does not claim raw-data reproduction.'];
end

function row = table_row(method, setup, meanX, stdX, relX, meanY, stdY, relY, meanQ, stdQ, relQ, meanH, stdH, relH)
row = struct();
row.method = method;
row.setup = setup;
row.mean_x_m = meanX;
row.std_x_m = stdX;
row.relative_error_x_percent = relX;
row.mean_y_m = meanY;
row.std_y_m = stdY;
row.relative_error_y_percent = relY;
row.mean_Q_gps = meanQ;
row.std_Q_gps = stdQ;
row.relative_error_Q_percent = relQ;
row.mean_Hr_m = meanH;
row.std_Hr_m = stdH;
row.relative_error_Hr_percent = relH;
end
