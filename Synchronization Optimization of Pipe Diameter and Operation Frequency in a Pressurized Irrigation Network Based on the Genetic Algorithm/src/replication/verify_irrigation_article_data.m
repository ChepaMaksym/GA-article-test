function report = verify_irrigation_article_data(xmlPath)
if nargin < 1 || isempty(xmlPath)
    xmlPath = irrigation_article_xml_path(find_project_root());
end

if ~isfile(xmlPath)
    error('Article XML was not found: %s', xmlPath);
end

xmlText = fileread(xmlPath);
metadata = article_metadata();
table2 = article_table2_original_branch_diameters();
table3 = article_table3_pipe_prices();
table5 = article_table5_model_performance();
table6 = article_table6_optimized_diameters();
savings = article_reported_savings();

checks = struct('name', {}, 'passed', {}, 'details', {});
checks(end + 1) = make_check('DOI is present in XML', contains(xmlText, metadata.doi), metadata.doi);
checks(end + 1) = make_check('MDPI URL is present in metadata', strcmp(metadata.url, 'https://www.mdpi.com/2077-0472/12/5/673'), metadata.url);
checks(end + 1) = make_check('Article title is encoded', contains(xmlText, 'Synchronization Optimization of Pipe Diameter'), metadata.title);
checks(end + 1) = make_check('Table 2 dimensions are 10 by 7', isequal(size(table2.diameter_mm), [10 7]), mat2str(size(table2.diameter_mm)));
checks(end + 1) = make_check('Table 2 branch 1 matches XML', isequaln(table2.diameter_mm(1, :), [160 200 250 250 315 315 315]), mat2str(table2.diameter_mm(1, :)));
checks(end + 1) = make_check('Table 3 commercial diameters match XML', isequal(table3.outside_diameter_mm, [140 160 200 250 315 400]), mat2str(table3.outside_diameter_mm));
checks(end + 1) = make_check('Table 3 prices match XML', isequal(table3.unit_price_yuan_per_m, [28 37 56 90 142 232]), mat2str(table3.unit_price_yuan_per_m));
checks(end + 1) = make_check('Table 5 has 15 model-sector rows', numel(table5) == 15, sprintf('%d rows', numel(table5)));
checks(end + 1) = make_check('Table 5 SOM sector 5 frequency is 43 Hz', find_table5_value(table5, 'SOM', 5, 'frequency_Hz') == 43, 'SOM sector 5');
checks(end + 1) = make_check('Table 6 PDM branch 1 matches XML', isequaln(table6.PDM(1, :), [200 200 200 200 200 200 200]), mat2str(table6.PDM(1, :)));
checks(end + 1) = make_check('Table 6 SOM branch 1 matches XML', isequaln(table6.SOM(1, :), [200 200 200 200 250 250 315]), mat2str(table6.SOM(1, :)));
checks(end + 1) = make_check('Table 6 source anomaly is preserved', table6.SOM(7, 7) == 2, 'SOM branch 7 segment 7 = 2');
checks(end + 1) = make_check('Reported savings are encoded', abs(savings.SOM_percent - 19.3) < 1e-9, sprintf('SOM %.1f%%', savings.SOM_percent));

warnings = {};
if ~contains(xmlText, 'appendix', 'IgnoreCase', true) && ~contains(xmlText, 'source code', 'IgnoreCase', true)
    warnings{end + 1} = 'The XML does not include Appendix MATLAB code or a source-code listing.';
end
if contains(xmlText, 'Fig5.tif') || contains(xmlText, 'Figure 5')
    warnings{end + 1} = 'The XML references Figure 5 network layout, but bundled .tif figure files are not present in the project.';
end
if any(table6.SOM(:) == 2)
    warnings{end + 1} = 'Table 6 contains an apparent source anomaly: SOM branch 7 segment 7 is 2 mm, not a commercial pipe diameter.';
end
warnings{end + 1} = 'Table 4 pump coefficients are partially represented around an ellipsis in the article table; encoded values preserve the visible XML entries.';
warnings{end + 1} = 'The executable GA sandbox is a surrogate model, not a full EPANET/MATLAB hydraulic reproduction.';

report = struct();
report.xml_path = xmlPath;
report.metadata = metadata;
report.checks = checks;
report.warnings = warnings;
report.passed = all([checks.passed]);
report.pass_count = nnz([checks.passed]);
report.warning_count = numel(warnings);
report.generated_at = char(datetime('now', 'Format', 'yyyy-MM-dd HH:mm:ss'));

fprintf('Irrigation article data checks: %d/%d passed.\n', nnz([checks.passed]), numel(checks));
if ~report.passed
    failed = checks(~[checks.passed]);
    for i = 1:numel(failed)
        fprintf('FAILED: %s (%s)\n', failed(i).name, failed(i).details);
    end
end
end

function check = make_check(name, passed, details)
check = struct('name', name, 'passed', logical(passed), 'details', details);
end

function value = find_table5_value(table5, model, sector, fieldName)
value = NaN;
for i = 1:numel(table5)
    row = table5(i);
    if strcmp(row.model, model) && row.sectoring == sector
        value = row.(fieldName);
        return;
    end
end
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
