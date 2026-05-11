function design = decode_building_genome(x, space)
if nargin < 2
    space = building_design_space();
end

x = repair_discrete_genome(x, space.bounds.lb, space.bounds.ub);

glazingIdx = x(1);
windowIdx = x(2:10);
wallIdx = x(11);
groundIdx = x(12);
ceilingIdx = x(13);
infiltrationIdx = x(14);
orientationIdx = x(15);

windowArea = space.window.area_options_m2(windowIdx);
orientation = space.orientation.options_deg(orientationIdx);
absoluteAzimuth = mod(space.window.base_azimuth_deg + orientation, 360);
southWeight = cosd(absoluteAzimuth - 180);
southWeight = max(0, southWeight);

design = struct();
design.genome = x;
design.glazing_idx = glazingIdx;
design.glazing_label = space.glazing.labels{glazingIdx};
design.u_window = space.glazing.u_window(glazingIdx);
design.shgc = space.glazing.shgc(glazingIdx);
design.tvis = space.glazing.tvis(glazingIdx);
design.glazing_cost_eur_m2 = space.glazing.cost_eur_m2(glazingIdx);
design.window_area_m2 = windowArea;
design.total_window_area_m2 = sum(windowArea);
design.total_glazing_area_m2 = design.total_window_area_m2 * space.window.glazing_area_ratio;
design.south_weighted_window_area_m2 = sum(windowArea .* southWeight);
design.south_fraction = safe_divide(design.south_weighted_window_area_m2, max(design.total_window_area_m2, eps));
design.wall_insulation_cm = space.insulation.wall_cm(wallIdx);
design.ground_insulation_cm = space.insulation.ground_cm(groundIdx);
design.ceiling_insulation_cm = space.insulation.ceiling_cm(ceilingIdx);
design.infiltration_h_1 = space.infiltration.options_h_1(infiltrationIdx);
design.orientation_deg = orientation;
design.absolute_window_azimuth_deg = absoluteAzimuth;
end

function value = safe_divide(a, b)
if abs(b) < eps
    value = 0;
else
    value = a ./ b;
end
end
