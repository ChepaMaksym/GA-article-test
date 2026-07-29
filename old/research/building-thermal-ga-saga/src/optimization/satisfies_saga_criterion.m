function report = satisfies_saga_criterion(result)
reasons = {};

if ~isfield(result, 'best_individual') || ~isfield(result.best_individual, 'x') || ~isfield(result.best_individual, 'theta')
    reasons{end + 1} = 'best individual does not contain both x and theta';
end

if ~isfield(result, 'diagnostics') || ~isfield(result.diagnostics, 'theta_in_genotype') || ~result.diagnostics.theta_in_genotype
    reasons{end + 1} = 'theta is not encoded in genotype';
end

if ~isfield(result.diagnostics, 'variation_receives_complete_individual') || ~result.diagnostics.variation_receives_complete_individual
    reasons{end + 1} = 'variation does not receive complete individuals';
end

if ~isfield(result.diagnostics, 'variation_changes_theta') || ~result.diagnostics.variation_changes_theta
    reasons{end + 1} = 'theta is not changed by variation';
end

if ~isfield(result.diagnostics, 'selection_returns_complete_individual') || ~result.diagnostics.selection_returns_complete_individual
    reasons{end + 1} = 'selection does not return complete individuals';
end

if isfield(result.diagnostics, 'external_theta_update') && result.diagnostics.external_theta_update
    reasons{end + 1} = 'theta is externally updated';
end

if isfield(result.diagnostics, 'generation_based_theta_update') && result.diagnostics.generation_based_theta_update
    reasons{end + 1} = 'theta uses generation-based update';
end

if isfield(result.diagnostics, 'stagnation_based_theta_update') && result.diagnostics.stagnation_based_theta_update
    reasons{end + 1} = 'theta uses stagnation-based update';
end

if isfield(result.diagnostics, 'diversity_based_theta_update') && result.diagnostics.diversity_based_theta_update
    reasons{end + 1} = 'theta uses diversity-based update';
end

if ~isfield(result, 'history') || ~isfield(result.history, 'theta_population_history')
    reasons{end + 1} = 'theta population history is missing';
end

report = struct();
report.passed = isempty(reasons);
report.reasons = reasons;
if report.passed
    report.message = 'formal SAGA criterion passed';
else
    report.message = ['Algorithm is not SAGA: ', strjoin(reasons, '; ')];
end
end
