projectRoot = fileparts(mfilename('fullpath'));
addpath(genpath(fullfile(projectRoot, 'src')));
addpath(fullfile(projectRoot, 'tests'));

structureReport = verify_project_structure(projectRoot);
testReport = run_unit_tests();
reproduction = run_ga_npw_reproduction();
sandbox = run_sandbox_deviation_check();

article = article_reported();
fprintf('Article: %s\n', article.title);
fprintf('DOI: %s\n\n', article.doi);

fprintf('Structure checks: %d passed, %d failed\n', structureReport.pass_count, structureReport.fail_count);
fprintf('Unit tests: %d passed\n\n', testReport.pass_count);

fprintf('GA-NPW synthetic reproduction\n');
fprintf('cases = %d\n', numel(reproduction.cases));
fprintf('mean NPW error = %.3f%%\n', reproduction.metrics.npw.mean_error_percent);
fprintf('mean GA-NPW error = %.3f%%\n', reproduction.metrics.ga_npw.mean_error_percent);
fprintf('report = %s\n\n', reproduction.report_path);

fprintf('Sandbox deviation check\n');
fprintf('cases = %d\n', numel(sandbox.cases));
fprintf('weighted NPW error = %.3f%%\n', sandbox.metrics.npw.weighted_mean_error_percent);
fprintf('weighted GA-NPW error = %.3f%%\n', sandbox.metrics.ga_npw.weighted_mean_error_percent);
fprintf('report = %s\n', sandbox.report_path);
