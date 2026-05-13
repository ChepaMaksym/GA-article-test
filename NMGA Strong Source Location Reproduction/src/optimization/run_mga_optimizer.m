function result = run_mga_optimizer(observation, options, generations)
if nargin < 2 || isempty(options)
    options = nmga_options('MGA', 'quick');
end
if nargin < 3 || isempty(generations)
    generations = options.MGAGenerations;
end
options.Method = 'MGA';
result = run_evolutionary_optimizer(observation, options, generations);
end
