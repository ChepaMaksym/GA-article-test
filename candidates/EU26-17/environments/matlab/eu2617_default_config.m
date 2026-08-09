function cfg = eu2617_default_config()
%EU2617_DEFAULT_CONFIG Frozen SupRB SAGA1 defaults and bounds.

cfg = struct();
cfg.v_min = 0.005;
cfg.v_max = 0.15;
cfg.mutation_rate_min = 0.001;
cfg.mutation_rate_max = 0.25;
cfg.mutation_rate_multiplier = 1.1;
cfg.crossover_rate_min = 0.5;
cfg.crossover_rate_max = 1.0;
cfg.crossover_rate_multiplier = 1.1;
end
