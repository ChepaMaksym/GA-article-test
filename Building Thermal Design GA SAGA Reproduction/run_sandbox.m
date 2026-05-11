function sandbox = run_sandbox()
projectRoot = fileparts(mfilename('fullpath'));
addpath(genpath(fullfile(projectRoot, 'src')));
sandbox = run_sandbox_impl();
end
