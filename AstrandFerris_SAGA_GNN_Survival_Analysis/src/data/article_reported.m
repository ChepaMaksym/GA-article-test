function reported = article_reported()
reported = struct();

reported.model.hidden_nodes = 2;
reported.model.hidden_activation = 'tanh';
reported.model.output_activation = 'linear';
reported.fitness = 'c_index_error';

reported.hyperparameters.initialisation_width = 1.0;
reported.hyperparameters.sigma1 = 1.0;
reported.hyperparameters.sigma2 = 1.0;
reported.hyperparameters.m = 2;
reported.hyperparameters.o = 0.5;
reported.hyperparameters.p = 0.9;
reported.hyperparameters.tau_rule = 'tau proportional to 1/(2*sqrt(n_weights))';
reported.hyperparameters.epsilon = 1.0e-3;

reported.mutation_width_updates = {'gaussian', 'exponential'};
reported.mutation_operators = {'EMO', 'GMO', 'MMO', 'AMMO'};
reported.self_adaptive_levels = {'sigma', 'sigma_m', 'sigma_m_o'};
reported.adaptive_sigma.survival_high = 0.30;
reported.adaptive_sigma.survival_low = 0.05;
reported.adaptive_sigma.upper_sigma_for_doubling = 3.0;
reported.adaptive_sigma.lower_sigma_for_halving = 1.0e-3;

reported.datasets = struct( ...
    'name', {'PBC_MAYO', 'LUNG', 'FLCHAIN', 'NWTCO'}, ...
    'feature_count', {17, 7, 7, 4}, ...
    'patient_count', {312, 228, 314, 309}, ...
    'event', {'death', 'death', 'death', 'relapse'});
end
