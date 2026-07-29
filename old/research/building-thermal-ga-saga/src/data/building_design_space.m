function space = building_design_space()
space = struct();

space.glazing.labels = {'G10', 'G07', 'G06', 'G05'};
space.glazing.u_window = [1.13, 0.90, 0.85, 0.78];
space.glazing.shgc = [0.49, 0.61, 0.51, 0.43];
space.glazing.tvis = [0.72, 0.73, 0.74, 0.65];
space.glazing.cost_eur_m2 = [34.4, 64.7, 53.5, 57.9];

space.window.height_m = 1.5;
space.window.width_options_m = [0, 0.75:0.25:4.25];
space.window.area_options_m2 = space.window.height_m .* space.window.width_options_m;
space.window.frame_install_cost_eur_m2 = 110;
space.window.glazing_area_ratio = 0.69;
space.window.minimum_glazing_area_m2 = 14.4;
space.window.base_azimuth_deg = [0, 0, 90, 90, 180, 180, 270, 270, 0];

space.insulation.wall_cm = [12, 15, 18, 20, 22, 25];
space.insulation.ground_cm = [5, 6, 8, 10, 12, 15];
space.insulation.ceiling_cm = [20, 22, 25, 28, 30, 35];
space.insulation.wall_cost_eur_m3 = 46.0;
space.insulation.ground_cost_eur_m3 = 51.9;
space.insulation.ceiling_cost_eur_m2_cm = 0.3;
space.insulation.wall_area_m2 = 102.15;
space.insulation.ground_area_m2 = 150;
space.insulation.ceiling_area_m2 = 150;

space.infiltration.options_h_1 = [0.3, 0.5, 0.7, 1.0];
space.orientation.options_deg = 0:22.5:337.5;

space.reference.glazing_idx = 1;
space.reference.window_area_m2 = [3.000, 0.000, 6.375, 2.250, 3.375, 0.750, 3.375, 4.125, 0.000];
space.reference.window_idx = window_area_to_indices(space.reference.window_area_m2, space.window.area_options_m2);
space.reference.wall_idx = 1;
space.reference.ground_idx = 1;
space.reference.ceiling_idx = 1;
space.reference.infiltration_idx = 2;
space.reference.orientation_idx = 1;
space.reference.floor_area_m2 = 150;

space.gene_names = [{'glazing'}, make_window_names(), {'wall_insulation', 'ground_insulation', ...
    'ceiling_insulation', 'infiltration', 'orientation'}];
space.reference.genome = [space.reference.glazing_idx, space.reference.window_idx, ...
    space.reference.wall_idx, space.reference.ground_idx, space.reference.ceiling_idx, ...
    space.reference.infiltration_idx, space.reference.orientation_idx];
space.bounds.lb = ones(1, numel(space.gene_names));
space.bounds.ub = [numel(space.glazing.labels), ...
    repmat(numel(space.window.area_options_m2), 1, 9), ...
    numel(space.insulation.wall_cm), numel(space.insulation.ground_cm), ...
    numel(space.insulation.ceiling_cm), numel(space.infiltration.options_h_1), ...
    numel(space.orientation.options_deg)];
end

function names = make_window_names()
names = cell(1, 9);
for i = 1:9
    names{i} = sprintf('window_%d', i);
end
end

function idx = window_area_to_indices(areaValues, areaOptions)
idx = zeros(1, numel(areaValues));
for i = 1:numel(areaValues)
    [~, idx(i)] = min(abs(areaOptions - areaValues(i)));
end
end
