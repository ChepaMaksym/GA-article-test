projectRoot = fileparts(mfilename('fullpath'));
addpath(genpath(fullfile(projectRoot, 'src')));
addpath(fullfile(projectRoot, 'tests'));

structureReport = verify_project_structure(projectRoot);
testReport = run_unit_tests();
reproduction = run_spso_ga_reproduction();
sandbox = run_sandbox_deviation_check();

article = article_reported();
fprintf('Article: %s\n', article.title);
fprintf('DOI: %s\n\n', article.doi);

fprintf('Structure checks: %d passed, %d failed\n', structureReport.pass_count, structureReport.fail_count);
fprintf('Unit tests: %d passed\n\n', testReport.pass_count);

fprintf('SPSO-GA synthetic reproduction\n');
fprintf('cases = %d\n', numel(reproduction.cases));
fprintf('PSO-GA accuracy = %.1f%%\n', reproduction.metrics.pso_ga.accuracy_percent);
fprintf('SPSO-GA accuracy = %.1f%%\n', reproduction.metrics.spso_ga.accuracy_percent);
fprintf('report = %s\n\n', reproduction.report_path);

fprintf('Sandbox deviation check\n');
fprintf('cases = %d\n', numel(sandbox.cases));
fprintf('SPSO-GA accuracy = %.1f%%\n', sandbox.summary.spso_ga_accuracy_percent);
fprintf('worst case = %s\n', sandbox.summary.worst_case);
fprintf('report = %s\n', sandbox.report_path);
