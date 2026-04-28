function results = evaluate_reported_designs()
% Evaluate source-table PDM/SOM branch-level summaries with the surrogate model.
table6 = article_table6_optimized_diameters();
table5 = article_table5_model_performance();

models = {'PDM', 'SOM'};
for i = 1:numel(models)
    model = models{i};
    diameterMatrix = table6.(model);
    branchDiameter = branch_mode_diameter(diameterMatrix);
    frequency = frequencies_for_model(table5, model);
    [objective, details] = irrigation_surrogate_objective([diameters_to_indices(branchDiameter), frequency]);
    results(i) = struct( ... %#ok<AGROW>
        'model', model, ...
        'branch_diameter_mm', branchDiameter, ...
        'frequency_Hz', frequency, ...
        'objective', objective, ...
        'network_cost', details.network_cost, ...
        'energy_cost', details.energy_cost, ...
        'penalty', details.penalty);
end
end

function branchDiameter = branch_mode_diameter(matrix)
prices = article_table3_pipe_prices();
validOptions = prices.outside_diameter_mm;
branchDiameter = zeros(1, size(matrix, 1));
for row = 1:size(matrix, 1)
    values = matrix(row, :);
    values = values(~isnan(values) & ismember(values, validOptions));
    branchDiameter(row) = mode(values);
end
end

function frequency = frequencies_for_model(rows, model)
frequency = zeros(1, 5);
for i = 1:numel(rows)
    if strcmp(rows(i).model, model)
        frequency(rows(i).sectoring) = rows(i).frequency_Hz;
    end
end
end

function idx = diameters_to_indices(diameters)
prices = article_table3_pipe_prices();
idx = zeros(1, numel(diameters));
for i = 1:numel(diameters)
    idx(i) = find(prices.outside_diameter_mm == diameters(i), 1);
end
end
