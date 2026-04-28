function result = run_sandbox_deviation_check()
projectRoot = fileparts(mfilename('fullpath'));
addpath(genpath(fullfile(projectRoot, 'src')));
result = run_sandbox_deviation_check_impl();
end
