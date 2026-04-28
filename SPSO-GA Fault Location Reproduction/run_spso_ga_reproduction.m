function result = run_spso_ga_reproduction()
projectRoot = fileparts(mfilename('fullpath'));
addpath(genpath(fullfile(projectRoot, 'src')));
result = run_spso_ga_reproduction_impl();
end
