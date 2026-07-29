function reported = article_reported()
reported = struct();

reported.reference.cooling.lcc_eur = 11236;
reported.reference.cooling.heating_kwh_m2 = 69.2;
reported.reference.cooling.cooling_kwh_m2 = 7.7;
reported.reference.no_cooling.lcc_eur = 10416;
reported.reference.no_cooling.heating_kwh_m2 = 69.0;
reported.reference.no_cooling.cooling_kwh_m2 = 0;

reported.ga.population_size = 50;
reported.ga.generations = 80;
reported.ga.encoding = 'value encoding';
reported.ga.article_selection = 'rank-based roulette wheel selection with power scaling';
reported.ga.article_crossover = 'uniform crossover';
reported.ga.article_mutation = 'add/subtract step mutation';

reported.article_sga.status_under_local_plan = 'non_saga_external_adaptation';
reported.article_sga.reason = ['The article calculates k, Pc, Pm, and S during the run from ', ...
    'chromosome diversity, simulation stage, and no-improvement count. ', ...
    'The local plan requires theta_base to be encoded inside the genotype.'];

reported.case_ids = 1:7;
reported.cooling_lcc_savings_percent = [5.9, 6.8, 10.6, 11.1, 16.2, 16.7, 34.2];
reported.no_cooling_lcc_savings_percent = [13.3, 15.5, 19.3, 20.9, 30.2, 31.7, 51.1];
reported.cooling_best_lcc_eur = round(reported.reference.cooling.lcc_eur .* ...
    (1 - reported.cooling_lcc_savings_percent ./ 100));
reported.no_cooling_best_lcc_eur = round(reported.reference.no_cooling.lcc_eur .* ...
    (1 - reported.no_cooling_lcc_savings_percent ./ 100));
end
