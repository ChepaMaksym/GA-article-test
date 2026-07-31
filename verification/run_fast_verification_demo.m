function report = run_fast_verification_demo(useParallel)
%RUN_FAST_VERIFICATION_DEMO Demonstrate decisive P2 failure with mock runs.

if nargin < 1
    useParallel = true;
end
root = fileparts(mfilename("fullpath"));
addpath(root);
cleanup = onCleanup(@() rmpath(root));
options = fastverify.default_options();
options.UseParallel = logical(useParallel);
options.CacheDirectory = fullfile(tempdir, "ga_fast_verification_demo");
options.AdapterFiles = [string(mfilename("fullpath")) + ".m"; ...
    string(which("fastverify.mock_adapter"))];
options.AdapterConfiguration = struct("scenario", "fail_p2");
adapter = @(runId, seed, target, prior) ...
    fastverify.mock_adapter(runId, seed, target, prior, "fail_p2");
contract = fastverify.bind_adapter( ...
    fastverify.usa001_contract(), adapter, options);
report = fastverify.run_staged(adapter, contract, options);
fprintf("Demo status: %s; stopped at generation %d\n", ...
    report.status, report.stoppedAtGeneration);
end
