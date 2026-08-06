function gesmr_validate_config(cfg)
%GESMR_VALIDATE_CONFIG Fail closed on ambiguous group/selection arithmetic.

required = { ...
    'non_elite_size', ...
    'n_groups', ...
    'solution_selection_rate', ...
    'mr_selection_rate', ...
    'meta_mutation_rate', ...
    'initial_log10_mr_min', ...
    'initial_log10_mr_max'};
for i = 1:numel(required)
    if ~isfield(cfg, required{i})
        error('gesmr:MissingConfig', 'Missing configuration field: %s', required{i});
    end
end

if ~is_scalar_integer(cfg.non_elite_size) || cfg.non_elite_size < 1
    error('gesmr:BadConfig', 'non_elite_size must be a positive integer');
end
if ~is_scalar_integer(cfg.n_groups) || cfg.n_groups < 1
    error('gesmr:BadConfig', 'n_groups must be a positive integer');
end
if mod(cfg.non_elite_size, cfg.n_groups) ~= 0
    error('gesmr:BadConfig', 'n_groups must divide non_elite_size exactly');
end
validate_selection(cfg.solution_selection_rate, cfg.non_elite_size, 'solution_selection_rate');
validate_selection(cfg.mr_selection_rate, cfg.n_groups, 'mr_selection_rate');
if ~isscalar(cfg.meta_mutation_rate) || ~isfinite(cfg.meta_mutation_rate) || cfg.meta_mutation_rate <= 0
    error('gesmr:BadConfig', 'meta_mutation_rate must be finite and positive');
end
if ~isscalar(cfg.initial_log10_mr_min) || ~isfinite(cfg.initial_log10_mr_min)
    error('gesmr:BadConfig', 'initial_log10_mr_min must be finite');
end
if ~isscalar(cfg.initial_log10_mr_max) || ~isfinite(cfg.initial_log10_mr_max)
    error('gesmr:BadConfig', 'initial_log10_mr_max must be finite');
end
if cfg.initial_log10_mr_min > cfg.initial_log10_mr_max
    error('gesmr:BadConfig', 'initial mutation-rate interval is reversed');
end
end

function validate_selection(rate, size_value, name)
if ~isscalar(rate) || ~isfinite(rate) || rate <= 0 || rate > 1
    error('gesmr:BadConfig', '%s must lie in (0, 1]', name);
end
count = rate * size_value;
if abs(count - round(count)) > 1e-12 || round(count) < 1
    error('gesmr:BadConfig', '%s times population size must be a positive integer', name);
end
end

function tf = is_scalar_integer(value)
tf = isscalar(value) && isfinite(value) && value == round(value);
end
