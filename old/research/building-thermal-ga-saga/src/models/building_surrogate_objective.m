function [objective, details] = building_surrogate_objective(x, problem)
x = apply_case_mask(x, problem);
design = decode_building_genome(x, problem.design_space);
details = synthetic_building_forward(design, problem);

penalty = constraint_penalty(design, problem);
details.penalty = penalty;
details.objective = details.lcc_eur + penalty;
details.data_class = problem.data_class;
objective = details.objective;
end

function penalty = constraint_penalty(design, problem)
space = problem.design_space;
penalty = 0;

glazingShortfall = space.window.minimum_glazing_area_m2 - design.total_glazing_area_m2;
if glazingShortfall > 0
    penalty = penalty + 2.0e5 * glazingShortfall.^2;
end

if any(design.window_area_m2([1, 3, 4, 5, 7, 8]) <= 0)
    penalty = penalty + 5.0e4;
end

if problem.no_cooling
    overheatingRisk = max(0, design.south_fraction * design.shgc * design.total_window_area_m2 / 23.25 - 0.46);
    penalty = penalty + 1000 * overheatingRisk.^2;
end
end
