function [objective, details] = source_objective(candidate, observation)
predicted = gaussian_plume_concentration(candidate, observation.sensors, observation.model_wind_speed_mps);
rawResidual = predicted - observation.observed_concentration;
rawSse = sum(rawResidual .^ 2);

if isfield(observation, 'objective_mode')
    objectiveMode = observation.objective_mode;
else
    objectiveMode = 'normalized_mse';
end

switch lower(objectiveMode)
    case 'article_sse'
        residual = rawResidual;
        objective = rawSse;
    case 'normalized_mse'
        scale = max(max(observation.observed_concentration), 1.0e-9);
        residual = rawResidual ./ scale;
        objective = mean(residual .^ 2);
    otherwise
        error('Unknown source objective mode: %s', objectiveMode);
end

if nargout > 1
    details = struct();
    details.objective_mode = objectiveMode;
    details.predicted_concentration = predicted;
    details.residual = residual;
    details.raw_residual = rawResidual;
    details.raw_sse = rawSse;
    details.article_style_fitness = 1 ./ max(rawSse, eps);
end
end
