function testReport = run_unit_tests()
projectRoot = fileparts(mfilename('fullpath'));
addpath(genpath(fullfile(projectRoot, 'src')));
addpath(fullfile(projectRoot, 'tests'));
testReport = run_unit_tests_impl();
end
