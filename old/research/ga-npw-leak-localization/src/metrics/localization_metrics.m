function metrics = localization_metrics(truePosition_m, predictedPosition_m, pipelineLength_m, weights)
if nargin < 4 || isempty(weights)
    weights = ones(size(truePosition_m));
end

truePosition_m = truePosition_m(:);
predictedPosition_m = predictedPosition_m(:);
weights = weights(:);
weights = weights ./ sum(weights);

deviation_m = abs(predictedPosition_m - truePosition_m);
error_percent = 100 * deviation_m ./ pipelineLength_m;

metrics = struct();
metrics.count = numel(truePosition_m);
metrics.mae_m = mean(deviation_m);
metrics.rmse_m = sqrt(mean(deviation_m .^ 2));
metrics.mean_error_percent = mean(error_percent);
metrics.std_error_percent = std(error_percent);
metrics.max_error_percent = max(error_percent);
metrics.weighted_mae_m = sum(weights .* deviation_m);
metrics.weighted_rmse_m = sqrt(sum(weights .* deviation_m .^ 2));
metrics.weighted_mean_error_percent = sum(weights .* error_percent);
metrics.error_percent = error_percent;
metrics.deviation_m = deviation_m;
end
