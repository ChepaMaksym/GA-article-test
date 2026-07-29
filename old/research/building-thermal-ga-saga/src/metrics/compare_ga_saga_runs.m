function summary = compare_ga_saga_runs(runs)
gaLcc = [runs.ga_lcc_eur];
sagaLcc = [runs.saga_lcc_eur];
deltaPercent = 100 * (sagaLcc - gaLcc) ./ gaLcc;

summary = struct();
summary.run_count = numel(runs);
summary.mean_ga_lcc = mean(gaLcc);
summary.mean_saga_lcc = mean(sagaLcc);
summary.best_mean_ga_lcc = min(gaLcc);
summary.best_mean_saga_lcc = min(sagaLcc);
summary.mean_delta_percent = mean(deltaPercent);
summary.saga_win_rate = mean(sagaLcc < gaLcc);
summary.all_saga_criteria_passed = all([runs.saga_criterion_passed]);
summary.note = 'Synthetic surrogate comparison under equal population/generation budgets.';
end
