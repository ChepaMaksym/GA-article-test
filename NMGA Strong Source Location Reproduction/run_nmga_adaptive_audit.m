function result = run_nmga_adaptive_audit(profile)
if nargin < 1 || isempty(profile)
    profile = 'quick';
end
projectRoot = fileparts(mfilename('fullpath'));
addpath(genpath(fullfile(projectRoot, 'src')));
result = run_nmga_adaptive_audit_impl(profile);
end
