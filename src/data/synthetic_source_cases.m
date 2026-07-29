function cases = synthetic_source_cases(kind)
if nargin < 1 || isempty(kind)
    kind = 'reproduction';
end

article = article_reported();
base = struct();
base.data_type = 'synthetic_reproduction';
base.name = 'baseline';
base.layout = 'figure_eight';
base.true_x_m = article.scenario.target_x_m;
base.true_y_m = article.scenario.target_y_m;
base.true_Q_gps = article.scenario.Q_gps;
base.true_H_m = article.scenario.Hr_m;
base.wind_speed_mps = article.scenario.wind_speed_mps;
base.model_wind_speed_mps = article.scenario.wind_speed_mps;
base.stability = article.scenario.stability;
base.noise_fraction = 0.0;
base.weight = 1.0;

if strcmpi(kind, 'unit')
    cases = base;
    return;
end

noisy = base;
noisy.name = 'noisy_concentrations';
noisy.noise_fraction = 0.06;
noisy.weight = 1.4;

few = base;
few.name = 'few_sensors';
few.layout = 'few_sensors';
few.noise_fraction = 0.02;
few.weight = 1.5;

windBias = base;
windBias.name = 'biased_wind_speed';
windBias.model_wind_speed_mps = 2.25;
windBias.noise_fraction = 0.03;
windBias.weight = 1.8;

shifted = base;
shifted.name = 'shifted_source';
shifted.true_x_m = -8;
shifted.true_y_m = 31;
shifted.noise_fraction = 0.02;
shifted.weight = 1.7;

highQ = base;
highQ.name = 'high_source_intensity';
highQ.true_Q_gps = 1.25 * base.true_Q_gps;
highQ.noise_fraction = 0.04;
highQ.weight = 1.3;

lowQ = base;
lowQ.name = 'low_source_intensity';
lowQ.true_Q_gps = 0.75 * base.true_Q_gps;
lowQ.noise_fraction = 0.04;
lowQ.weight = 1.3;

cases = [base, noisy, few, windBias, shifted, highQ, lowQ];

if strcmpi(kind, 'sandbox')
    return;
elseif strcmpi(kind, 'reproduction')
    cases = base;
else
    error('Unknown synthetic case kind: %s', kind);
end
end
