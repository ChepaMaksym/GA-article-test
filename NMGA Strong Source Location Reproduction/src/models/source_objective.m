function [objective, details] = source_objective(candidate, observation)
predicted = gaussian_plume_concentration(candidate, observation.sensors, observation.model_wind_speed_mps);
scale = max(max(observation.observed_concentration), 1.0e-9);
residual = (predicted - observation.observed_concentration) ./ scale;
objective = mean(residual .^ 2);

if nargout > 1
    details = struct();
    details.predicted_concentration = predicted;
    details.residual = residual;
    details.article_style_fitness = 1 ./ max(sum((predicted - observation.observed_concentration) .^ 2), eps);
end
end
