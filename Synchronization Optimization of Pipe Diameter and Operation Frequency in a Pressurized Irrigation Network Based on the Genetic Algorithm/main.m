projectRoot = fileparts(mfilename('fullpath'));
addpath(genpath(fullfile(projectRoot, 'src')));

xmlPath = irrigation_article_xml_path(projectRoot);
report = verify_irrigation_article_data(xmlPath);
gaResult = run_ga_irrigation_sandbox();
replication = run_replication_study();

metadata = article_metadata();
fprintf('Article: %s\n', metadata.title);
fprintf('DOI: %s\n\n', metadata.doi);

fprintf('Consistency checks: %d passed, %d warnings\n', report.pass_count, report.warning_count);
for i = 1:numel(report.warnings)
    fprintf('Warning: %s\n', report.warnings{i});
end
fprintf('\n');

fprintf('GA sandbox result\n');
fprintf('method = %s\n', gaResult.method);
fprintf('model = %s\n', gaResult.model);
fprintf('best objective = %.6f\n', gaResult.best_objective);
fprintf('selected frequencies = [%s] Hz\n', strjoin(compose('%.0f', gaResult.best_frequency_Hz), ', '));
fprintf('selected branch diameters = [%s] mm\n\n', strjoin(compose('%.0f', gaResult.best_branch_diameter_mm), ', '));

fprintf('Replication report: %s\n', replication.report_path);
fprintf('GA report: %s\n', gaResult.report_path);
