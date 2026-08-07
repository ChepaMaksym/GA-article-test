function sigmas = gesmr_initial_mutation_rates(cfg)
%GESMR_INITIAL_MUTATION_RATES Logarithmic MR population from 1e-3 to 1e3.

if nargin < 1 || isempty(cfg)
    cfg = gesmr_default_config();
end
gesmr_validate_config(cfg);
sigmas = (10 .^ linspace( ...
    cfg.initial_log10_mr_min, ...
    cfg.initial_log10_mr_max, ...
    cfg.n_groups))';
end
