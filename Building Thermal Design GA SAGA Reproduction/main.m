projectRoot = fileparts(mfilename('fullpath'));
addpath(genpath(fullfile(projectRoot, 'src')));
addpath(fullfile(projectRoot, 'tests'));

structureReport = verify_project_structure(projectRoot);
testReport = run_unit_tests();
reproduction = run_reproduction();
sandbox = run_sandbox();

article = article_metadata();
fprintf('Article: %s\n', article.title);
fprintf('DOI: %s\n\n', article.doi);

fprintf('Structure checks: %d passed, %d failed\n', structureReport.pass_count, structureReport.fail_count);
fprintf('Unit tests: %d passed\n\n', testReport.pass_count);

fprintf('GA vs formal SAGA reproduction\n');
fprintf('runs = %d\n', numel(reproduction.runs));
fprintf('best mean classical GA LCC = %.3f EUR\n', reproduction.summary.best_mean_ga_lcc);
fprintf('best mean formal SAGA LCC = %.3f EUR\n', reproduction.summary.best_mean_saga_lcc);
fprintf('report = %s\n\n', reproduction.report_path);

fprintf('Sandbox SAGA criterion check\n');
fprintf('scenarios = %d\n', numel(sandbox.scenarios));
fprintf('all formal SAGA checks passed = %d\n', sandbox.all_saga_checks_passed);
fprintf('report = %s\n', sandbox.report_path);
