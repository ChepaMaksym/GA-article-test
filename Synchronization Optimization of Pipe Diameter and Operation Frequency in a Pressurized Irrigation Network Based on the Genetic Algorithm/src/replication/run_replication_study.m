function replication = run_replication_study()
projectRoot = find_project_root();
resultsDir = fullfile(projectRoot, 'sandbox', 'results');
if ~exist(resultsDir, 'dir')
    mkdir(resultsDir);
end

xmlPath = irrigation_article_xml_path(projectRoot);
checkReport = verify_irrigation_article_data(xmlPath);
metadata = article_metadata();
basic = article_basic_information();
table1 = article_table1_rotation_sectoring();
table2 = article_table2_original_branch_diameters();
table3 = article_table3_pipe_prices();
table5 = article_table5_model_performance();
table6 = article_table6_optimized_diameters();
savings = article_reported_savings();
reportedDesigns = evaluate_reported_designs();

gaResult = [];
gaMatPath = fullfile(resultsDir, 'ga_sandbox_result.mat');
if isfile(gaMatPath)
    loaded = load(gaMatPath, 'result');
    gaResult = loaded.result;
else
    gaResult = run_ga_irrigation_sandbox();
end

replication = struct();
replication.metadata = metadata;
replication.basic_information = basic;
replication.check_report = checkReport;
replication.table1 = table1;
replication.table2 = table2;
replication.table3 = table3;
replication.table5 = table5;
replication.table6 = table6;
replication.reported_savings = savings;
replication.reported_designs_surrogate = reportedDesigns;
replication.ga_sandbox = gaResult;
replication.report_path = fullfile(resultsDir, 'replication_report.md');
replication.mat_path = fullfile(resultsDir, 'replication_report.mat');
replication.status = replication_status(checkReport);

save(replication.mat_path, 'replication');
write_replication_report(replication);

fprintf('Replication report written to: %s\n', replication.report_path);
fprintf('Replication MAT written to: %s\n', replication.mat_path);
end

function status = replication_status(checkReport)
if checkReport.passed
    status = 'Article-backed data checks passed; full hydraulic reproduction remains blocked by missing layout/source-code inputs.';
else
    status = 'One or more article-backed data checks failed; inspect replication_report.md before using results.';
end
end

function write_replication_report(replication)
fid = fopen(replication.report_path, 'w');
if fid == -1
    error('Cannot open replication report for writing: %s', replication.report_path);
end
cleanupObj = onCleanup(@() fclose(fid)); %#ok<NASGU>

metadata = replication.metadata;
basic = replication.basic_information;
savings = replication.reported_savings;

fprintf(fid, '# Replication Report\n\n');
fprintf(fid, '## Article Resource\n');
fprintf(fid, '- Title: %s\n', metadata.title);
fprintf(fid, '- Authors: %s\n', strjoin(metadata.authors, ', '));
fprintf(fid, '- Journal: %s, %d, Article %d\n', metadata.journal, metadata.year, metadata.article_number);
fprintf(fid, '- DOI: `%s`\n', metadata.doi);
fprintf(fid, '- URL: %s\n\n', metadata.url);

fprintf(fid, '## Replication Scope\n');
fprintf(fid, 'This package separates two layers of work:\n\n');
fprintf(fid, '1. Article-backed checks that encode and verify tables and constants from the bundled XML.\n');
fprintf(fid, '2. An executable GA sandbox that demonstrates the optimization workflow with a simplified surrogate objective.\n\n');
fprintf(fid, 'A full numerical hydraulic reproduction is not claimed because the XML does not bundle the complete Figure 5 network geometry, pipe lengths, hydrant elevations, source MATLAB code, or an EPANET input model.\n\n');

fprintf(fid, '## Article-Backed Inputs\n');
fprintf(fid, '- Study area: %.0f ha\n', basic.irrigation_area_ha);
fprintf(fid, '- Annual irrigation quota: %.0f mm\n', basic.annual_irrigation_amount_mm);
fprintf(fid, '- Branch pipes: %d\n', basic.branch_pipe_count);
fprintf(fid, '- Main pipe diameter: %.0f mm\n', basic.main_pipe_diameter_mm);
fprintf(fid, '- Commercial U-PVC diameters: `[%s]` mm\n', strjoin(compose('%.0f', replication.table3.outside_diameter_mm), ' '));
fprintf(fid, '- Pipe prices: `[%s]` yuan/m\n\n', strjoin(compose('%.0f', replication.table3.unit_price_yuan_per_m), ' '));

fprintf(fid, '## Encoded Paper Results\n');
fprintf(fid, '- Reported OFM saving: %.1f%%\n', savings.OFM_percent);
fprintf(fid, '- Reported PDM saving: %.1f%%\n', savings.PDM_percent);
fprintf(fid, '- Reported SOM saving: %.1f%%\n', savings.SOM_percent);
fprintf(fid, '- Reported conclusion: synchronized optimization of pipe diameter and operation frequency gives the largest annual-cost reduction.\n\n');

fprintf(fid, '## Consistency Checks\n');
checks = replication.check_report.checks;
for i = 1:numel(checks)
    mark = 'PASS';
    if ~checks(i).passed
        mark = 'FAIL';
    end
    fprintf(fid, '- `%s`: %s. %s\n', mark, checks(i).name, checks(i).details);
end
fprintf(fid, '\n');

fprintf(fid, '## Warnings And Known Limitations\n');
for i = 1:numel(replication.check_report.warnings)
    fprintf(fid, '- %s\n', replication.check_report.warnings{i});
end
fprintf(fid, '\n');

fprintf(fid, '## GA Sandbox Result\n');
ga = replication.ga_sandbox;
fprintf(fid, '- Optimizer: `%s`\n', ga.method);
fprintf(fid, '- Best surrogate objective: `%.6f`\n', ga.best_objective);
fprintf(fid, '- Best branch diameters: `[%s]` mm\n', strjoin(compose('%.0f', ga.best_branch_diameter_mm), ' '));
fprintf(fid, '- Best frequencies: `[%s]` Hz\n', strjoin(compose('%.0f', ga.best_frequency_Hz), ' '));
fprintf(fid, '- Sandbox report: `sandbox/results/ga_sandbox_report.md`\n\n');

fprintf(fid, '## Reported Designs Re-Evaluated In Sandbox Surrogate\n');
for i = 1:numel(replication.reported_designs_surrogate)
    row = replication.reported_designs_surrogate(i);
    fprintf(fid, '- `%s`: objective `%.6f`, network `%.6f`, energy `%.6f`, penalty `%.6f`\n', ...
        row.model, row.objective, row.network_cost, row.energy_cost, row.penalty);
end
fprintf(fid, '\n## Status\n%s\n', replication.status);
end

function projectRoot = find_project_root()
currentDir = fileparts(mfilename('fullpath'));
projectRoot = currentDir;
while ~isfile(fullfile(projectRoot, 'main.m'))
    parentDir = fileparts(projectRoot);
    if strcmp(parentDir, projectRoot)
        error('Project root with main.m was not found.');
    end
    projectRoot = parentDir;
end
end
