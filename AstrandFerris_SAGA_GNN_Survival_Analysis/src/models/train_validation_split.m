function split = train_validation_split(dataset, seed, validationFraction)
if nargin < 3
    validationFraction = 0.33;
end
rng(seed, 'twister');
n = dataset.patient_count;
idx = randperm(n);
nValidation = max(1, round(validationFraction * n));
validationIdx = idx(1:nValidation);
trainIdx = idx(nValidation + 1:end);

split = struct();
split.train = subset_dataset(dataset, trainIdx);
split.validation = subset_dataset(dataset, validationIdx);
end

function out = subset_dataset(dataset, idx)
out = dataset;
out.X = dataset.X(idx, :);
out.time = dataset.time(idx);
out.event = dataset.event(idx);
out.patient_count = numel(idx);
end
