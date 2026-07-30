function spec = article_exact_spec()
spec = struct();
spec.data_type = 'article_public_text_spec';
spec.replication_claim = 'public-text exact replication; raw monitoring data and exact sensor coordinates unavailable';

spec.source.title = 'Application of New Modified Genetic Algorithm in Inverse Calculation of Strong Source Location';
spec.source.doi = '10.3390/atmos14010089';
spec.source.url = 'https://www.mdpi.com/2073-4433/14/1/89';
spec.source.data_availability = 'Data sharing is not applicable to this article.';

spec.scenario.Q_gps = 15178.32;
spec.scenario.Hr_m = 2;
spec.scenario.wind_speed_mps = 2.0;
spec.scenario.stability = 'E';
spec.scenario.target_x_m = -25;
spec.scenario.target_y_m = 16;

spec.algorithm.population_size = 100;
spec.algorithm.mga_generations = 2000;
spec.algorithm.nmga_generations = [1000, 500];
spec.algorithm.mga_crossover_rate = 0.6;
spec.algorithm.mga_mutation_rate = 0.01;
spec.algorithm.nmga_initial_crossover_rate = 0.6;
spec.algorithm.nmga_initial_mutation_rate = 0.01;
spec.algorithm.schedule_exponent = 2;
spec.algorithm.beta = 0.7;
spec.algorithm.gamma = 0.5;
spec.algorithm.SetMax = 20;
spec.algorithm.tournament_size = 3;
spec.algorithm.chromosome = {'x_m', 'y_m', 'Q_gps', 'H_m'};

spec.objective.mode = 'article_sse';
spec.objective.optimization_direction = 'minimize sum squared residuals; equivalent to maximizing reciprocal fitness';
spec.objective.article_fitness = 'max f_obj = 1 / sum_i (C_obs_i - C_cal_i)^2';

spec.formulas.initial_gene = 'X_k = U_min^k + rand * (U_max^k - U_min^k)';
spec.formulas.crossover_rate = 'Pc = P1 * (1 - gen / maxgen)^b';
spec.formulas.mutation_rate = 'Pm = P2 * (1 + gen / maxgen)^b';
spec.formulas.nonuniform_delta = 'Delta(gen,u) = u * (1 - r^((1 - gen / maxgen)^b))';
spec.formulas.egp_crossover = 'AGP:EGP inheritance ratio 1:0.3 in NMGA public-text operator description';

spec.bounds.lb = [-80, -40, 5000, 0.5];
spec.bounds.ub = [40, 70, 25000, 8.0];
spec.bounds.provenance = 'Local reproducible bounds for unavailable raw article monitoring setup.';

spec.table1 = [ ...
    table_row('MGA', '100 x 2000', 49.86, 1.04, 2.08, 25.02, 0.08, 0.32, 10442.96, 55.40, 0.53, NaN, NaN, NaN); ...
    table_row('NMGA', '100 x 1000', -25.0000, 7.96e-12, 5.46e-14, 16.0000, 5.32e-13, 5.71e-15, 15178.00, 1.46e-9, 1.43e-14, 2.0000, 4.4e-13, 3.7e-14); ...
    table_row('NMGA', '100 x 500', -24.9719, 0.25, 0.11, 16.0081, 0.02, 0.011, 15173.00, 42.24, 0.038, 1.9981, 0.02, 0.094)];
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
