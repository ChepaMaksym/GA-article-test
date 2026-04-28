function metrics = fault_location_metrics(trueSections, predictedSections, weights)
if nargin < 3 || isempty(weights)
    weights = ones(size(trueSections));
end
trueSections = trueSections(:);
predictedSections = predictedSections(:);
weights = weights(:);
weights = weights ./ sum(weights);

sectionError = abs(predictedSections - trueSections);
metrics = struct();
metrics.count = numel(trueSections);
metrics.accuracy_percent = 100 * mean(sectionError == 0);
metrics.mean_section_error = mean(sectionError);
metrics.max_section_error = max(sectionError);
metrics.weighted_accuracy_percent = 100 * sum(weights .* (sectionError == 0));
metrics.weighted_mean_section_error = sum(weights .* sectionError);
metrics.section_error = sectionError;
end
