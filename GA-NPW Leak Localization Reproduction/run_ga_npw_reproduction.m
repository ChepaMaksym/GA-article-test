function result = run_ga_npw_reproduction()
projectRoot = fileparts(mfilename('fullpath'));
addpath(genpath(fullfile(projectRoot, 'src')));
result = run_ga_npw_reproduction_impl();
end
