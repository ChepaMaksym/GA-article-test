function result = run_nmga_optimizer(observation, options, generations)
if nargin < 2 || isempty(options)
    options = nmga_options('NMGA', 'quick');
end
if nargin < 3 || isempty(generations)
    generations = options.NMGA500Generations;
end
options.Method = 'NMGA';
result = run_evolutionary_optimizer(observation, options, generations);
end
