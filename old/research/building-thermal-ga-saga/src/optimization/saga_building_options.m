function options = saga_building_options(seed)
if nargin < 1
    seed = 20260503;
end

options = ga_building_options(seed);
options.GenotypeType = 'x_theta';
options.ThetaBounds.Pm = [0.02, 0.35];
options.ThetaBounds.Pc = [0.55, 0.95];
options.ThetaBounds.sigma = [0.50, 3.00];
options.ThetaMutationRate = 0.35;
options.ThetaMutationScale = [0.045, 0.045, 0.35];
options.InitialTheta.Pm = 0.08;
options.InitialTheta.Pc = 0.85;
options.InitialTheta.sigma = 1.4;
end
