function [gaOptions, sagaOptions] = configure_options_for_scenario(seed, scenario)
gaOptions = ga_building_options(seed);
sagaOptions = saga_building_options(seed);

switch scenario.option_mode
    case 'small_population'
        gaOptions.PopulationSize = 24;
        sagaOptions.PopulationSize = 24;
    case 'short_run'
        gaOptions.MaxGenerations = 32;
        sagaOptions.MaxGenerations = 32;
    case 'wide_theta'
        sagaOptions.ThetaBounds.Pm = [0.005, 0.50];
        sagaOptions.ThetaBounds.Pc = [0.30, 0.99];
        sagaOptions.ThetaBounds.sigma = [0.25, 5.00];
    otherwise
end
end
