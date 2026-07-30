function metrics = source_estimation_metrics(trueSource, estimatedSource)
delta = estimatedSource(:)' - trueSource(:)';
metrics = struct();
metrics.position_error_m = hypot(delta(1), delta(2));
metrics.x_error_m = abs(delta(1));
metrics.y_error_m = abs(delta(2));
metrics.Q_error_gps = abs(delta(3));
metrics.Q_relative_error_percent = 100 * abs(delta(3)) / max(abs(trueSource(3)), eps);
metrics.H_error_m = abs(delta(4));
metrics.H_relative_error_percent = 100 * abs(delta(4)) / max(abs(trueSource(4)), eps);
end
