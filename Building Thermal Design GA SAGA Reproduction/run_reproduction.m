function reproduction = run_reproduction()
projectRoot = fileparts(mfilename('fullpath'));
addpath(genpath(fullfile(projectRoot, 'src')));
reproduction = run_reproduction_impl();
end
