function details = synthetic_building_forward(design, problem)
space = problem.design_space;
reported = problem.reported;
scenario = problem.scenario;

if problem.no_cooling
    ref = reported.reference.no_cooling;
else
    ref = reported.reference.cooling;
end

refDesign = decode_building_genome(space.reference.genome, space);
areaRatio = safe_divide(design.total_window_area_m2, refDesign.total_window_area_m2);
solar = safe_divide(design.south_weighted_window_area_m2 * design.shgc, ...
    refDesign.south_weighted_window_area_m2 * refDesign.shgc);
windowLoss = areaRatio * design.u_window / refDesign.u_window;

wallFactor = refDesign.wall_insulation_cm / design.wall_insulation_cm;
groundFactor = refDesign.ground_insulation_cm / design.ground_insulation_cm;
ceilingFactor = refDesign.ceiling_insulation_cm / design.ceiling_insulation_cm;
insulationHeat = 0.45 * wallFactor + 0.25 * groundFactor + 0.30 * ceilingFactor;
insulationHeat = max(0.45, min(1.25, insulationHeat));

infiltrationHeat = 0.75 + 0.25 * design.infiltration_h_1 / refDesign.infiltration_h_1;
orientationTerm = scenario.orientation_bias * cosd(design.orientation_deg - 180);

heating = ref.heating_kwh_m2;
heating = heating * (0.62 * insulationHeat + 0.23 * infiltrationHeat + 0.15 * windowLoss);
heating = heating - 7.5 * (solar - 1) + 2.0 * orientationTerm;
heating = max(20, heating);

cooling = ref.cooling_kwh_m2;
if problem.no_cooling
    cooling = 0;
else
    cooling = cooling * (0.72 + 0.28 * max(0.55, 1.0 / insulationHeat));
    cooling = cooling + 5.5 * (solar - 1) + 1.2 * (areaRatio - 1);
    cooling = cooling - 1.6 * (design.infiltration_h_1 - refDesign.infiltration_h_1);
    cooling = cooling - 0.7 * orientationTerm;
    cooling = max(0.5, cooling);
end

heating = heating * scenario.energy_scale;
cooling = cooling * scenario.energy_scale;

dIC = incremental_investment_cost(design, refDesign, space);
lcc = life_cycle_cost(heating, cooling, dIC, problem);

noise = deterministic_noise(design.genome, scenario.deterministic_noise, lcc);
lcc = lcc + noise;

details = struct();
details.heating_kwh_m2 = heating;
details.cooling_kwh_m2 = cooling;
details.incremental_investment_cost_eur = dIC;
details.lcc_eur = lcc;
details.total_window_area_m2 = design.total_window_area_m2;
details.total_glazing_area_m2 = design.total_glazing_area_m2;
details.south_fraction = design.south_fraction;
details.glazing_label = design.glazing_label;
details.orientation_deg = design.orientation_deg;
details.insulation_cm = [design.wall_insulation_cm, design.ground_insulation_cm, design.ceiling_insulation_cm];
details.infiltration_h_1 = design.infiltration_h_1;
end

function dIC = incremental_investment_cost(design, refDesign, space)
glazingDelta = (design.glazing_cost_eur_m2 - refDesign.glazing_cost_eur_m2) * design.total_window_area_m2;
windowDelta = space.window.frame_install_cost_eur_m2 * ...
    (design.total_window_area_m2 - refDesign.total_window_area_m2);

wallDeltaM = (design.wall_insulation_cm - refDesign.wall_insulation_cm) / 100;
groundDeltaM = (design.ground_insulation_cm - refDesign.ground_insulation_cm) / 100;
ceilingDeltaCm = design.ceiling_insulation_cm - refDesign.ceiling_insulation_cm;

wallDelta = wallDeltaM * space.insulation.wall_area_m2 * space.insulation.wall_cost_eur_m3;
groundDelta = groundDeltaM * space.insulation.ground_area_m2 * space.insulation.ground_cost_eur_m3;
ceilingDelta = ceilingDeltaCm * space.insulation.ceiling_area_m2 * space.insulation.ceiling_cost_eur_m2_cm;
dIC = glazingDelta + windowDelta + wallDelta + groundDelta + ceilingDelta;
end

function noise = deterministic_noise(x, amplitude, lcc)
if amplitude <= 0
    noise = 0;
    return;
end
weights = primes(60);
weights = weights(1:numel(x));
phase = sum(double(x(:))' .* weights);
noise = amplitude * lcc * sin(phase);
end

function value = safe_divide(a, b)
if abs(b) < eps
    value = 1;
else
    value = a ./ b;
end
end
