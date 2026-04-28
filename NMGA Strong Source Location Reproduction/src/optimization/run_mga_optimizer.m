function result = run_mga_optimizer(observation, options)
if nargin < 2 || isempty(options)
    options = nmga_options('MGA', 'quick');
end
options.Method = 'MGA';
result = run_evolutionary_optimizer(observation, options, options.MGAGenerations);
end
