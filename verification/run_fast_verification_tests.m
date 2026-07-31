function results = run_fast_verification_tests()
%RUN_FAST_VERIFICATION_TESTS Execute the fail-closed harness test suite.

root = fileparts(mfilename("fullpath"));
addpath(root);
cleanup = onCleanup(@() rmpath(root));
suite = testsuite(fullfile(root, "tests"), "IncludeSubfolders", true);
results = run(suite);
disp(table(results));
if ~all([results.Passed])
    error("fastverify:TestsFailed", "%d of %d tests failed.", ...
        nnz(~[results.Passed]), numel(results));
end
fprintf("All %d fast-verification tests passed.\n", numel(results));
end
