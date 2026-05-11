function scenarios = synthetic_sandbox_scenarios()
scenarios = repmat(empty_scenario(), 1, 8);
scenarios(1) = make_scenario('baseline_clean', 1.0, 0, 0, 'default');
scenarios(2) = make_scenario('low_noise', 1.0, 0.015, 0, 'default');
scenarios(3) = make_scenario('high_noise', 1.0, 0.045, 0, 'default');
scenarios(4) = make_scenario('small_population', 1.0, 0, 0, 'small_population');
scenarios(5) = make_scenario('short_run', 1.0, 0, 0, 'short_run');
scenarios(6) = make_scenario('wide_theta_bounds', 1.0, 0, 0, 'wide_theta');
scenarios(7) = make_scenario('boundary_optimum', 0.82, 0, -0.18, 'default');
scenarios(8) = make_scenario('ill_scaled_variables', 1.18, 0.02, 0.12, 'default');
end

function scenario = empty_scenario()
scenario = struct('name', '', 'energy_scale', 1, 'deterministic_noise', 0, ...
    'orientation_bias', 0, 'option_mode', 'default');
end

function scenario = make_scenario(name, energyScale, deterministicNoise, orientationBias, optionMode)
scenario = empty_scenario();
scenario.name = name;
scenario.energy_scale = energyScale;
scenario.deterministic_noise = deterministicNoise;
scenario.orientation_bias = orientationBias;
scenario.option_mode = optionMode;
end
