projectRoot = fileparts(mfilename('fullpath'));
addpath(genpath(fullfile(projectRoot, 'src')));
addpath(fullfile(projectRoot, 'tests'));

structureReport = verify_project_structure(projectRoot);
testReport = run_unit_tests();
reproduction = run_nmga_reproduction();
adaptiveAudit = run_nmga_adaptive_audit('unit');
sandbox = run_sandbox_deviation_check();

article = article_reported();
fprintf('Article: %s\n', article.title);
fprintf('DOI: %s\n\n', article.doi);

fprintf('Structure checks: %d passed, %d failed\n', structureReport.pass_count, structureReport.fail_count);
fprintf('Unit tests: %d passed\n\n', testReport.pass_count);

fprintf('NMGA synthetic reproduction\n');
fprintf('profile = %s\n', reproduction.profile);
fprintf('repeats = %d\n', reproduction.repeat_count);
fprintf('MGA mean position error = %.3f m\n', reproduction.metrics.mga.mean_position_error_m);
fprintf('NMGA-500 mean position error = %.3f m\n', reproduction.metrics.nmga_500.mean_position_error_m);
fprintf('report = %s\n\n', reproduction.report_path);

fprintf('NMGA adaptive audit\n');
fprintf('profile = %s\n', adaptiveAudit.profile);
fprintf('cases = %d\n', numel(adaptiveAudit.cases));
fprintf('baseline median position error = %.3f m\n', adaptiveAudit.acceptance.baseline_median_position_error_m);
fprintf('scheduled rate check = %d\n', adaptiveAudit.acceptance.rate_schedule_passed);
fprintf('report = %s\n\n', adaptiveAudit.report_path);

fprintf('Sandbox deviation check\n');
fprintf('cases = %d\n', numel(sandbox.cases));
fprintf('baseline position error = %.3f m\n', sandbox.summary.baseline_position_error_m);
fprintf('worst position error = %.3f m\n', sandbox.summary.worst_position_error_m);
fprintf('report = %s\n', sandbox.report_path);
