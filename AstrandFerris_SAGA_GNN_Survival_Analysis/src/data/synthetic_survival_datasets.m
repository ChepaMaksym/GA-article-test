function datasets = synthetic_survival_datasets(nameFilter)
if nargin < 1
    nameFilter = '';
end

reported = article_reported();
defs = reported.datasets;
datasets = repmat(empty_dataset(), 1, numel(defs));

for i = 1:numel(defs)
    datasets(i) = make_dataset(defs(i).name, defs(i).feature_count, defs(i).patient_count, 9100 + i);
end

if ~isempty(nameFilter)
    keep = false(1, numel(datasets));
    for i = 1:numel(datasets)
        keep(i) = strcmpi(datasets(i).name, nameFilter);
    end
    datasets = datasets(keep);
end
end

function data = empty_dataset()
data = struct('name', '', 'feature_count', [], 'patient_count', [], ...
    'X', [], 'time', [], 'event', [], 'data_class', 'synthetic_reproduction');
end

function data = make_dataset(name, featureCount, patientCount, seed)
rng(seed, 'twister');
X = randn(patientCount, featureCount);
for j = 1:featureCount
    X(:, j) = X(:, j) + 0.25 * sin((1:patientCount)' * (j + 1) / 13);
end
X = normalize_columns(X);

beta = linspace(0.85, -0.35, featureCount)';
latentRisk = X * beta + 0.35 * tanh(X(:, 1)) - 0.2 * X(:, min(3, featureCount)).^2;
baseTime = 14 + 8 * rand(patientCount, 1);
eventTime = baseTime .* exp(-0.35 * latentRisk + 0.2 * randn(patientCount, 1));
censorTime = 14 + 11 * rand(patientCount, 1);
time = min(eventTime, censorTime);
event = double(eventTime <= censorTime);

data = empty_dataset();
data.name = name;
data.feature_count = featureCount;
data.patient_count = patientCount;
data.X = X;
data.time = time;
data.event = event;
end

function X = normalize_columns(X)
mu = mean(X, 1);
sigma = std(X, 0, 1);
sigma(sigma == 0) = 1;
X = (X - mu) ./ sigma;
end
