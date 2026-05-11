function classification = classify_article_sga()
classification = struct();
classification.name = 'article_fuzzy_sga';
classification.local_plan_class = 'non_saga_external_adaptation';
classification.is_formal_saga = false;
classification.theta_encoded_in_genotype = false;
classification.theta_changes_through_variation = false;
classification.selection_acts_on_x_theta = false;
classification.external_theta_update = true;
classification.external_signals = {'chromosome_diversity', 'simulation_stage', 'generations_with_no_improvement'};
classification.reason = ['The article states that k, Pc, S, and Pm are calculated automatically ', ...
    'during the run from diversity, stage, and no-improvement count by a fuzzy controller. ', ...
    'The local criterion requires theta_base to be part of the genotype and varied by genetic variation.'];
end
