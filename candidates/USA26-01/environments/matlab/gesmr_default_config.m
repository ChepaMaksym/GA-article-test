function cfg = gesmr_default_config()
%GESMR_DEFAULT_CONFIG Paper-grounded defaults for analytic GESMR runs.
% N is the number of non-elite solutions; the full population is N+1.

cfg = struct();
cfg.non_elite_size = 100;
cfg.n_groups = 10;
cfg.solution_selection_rate = 0.5;
cfg.mr_selection_rate = 0.5;
cfg.meta_mutation_rate = 2.0;
cfg.initial_log10_mr_min = -3.0;
cfg.initial_log10_mr_max = 3.0;
end
