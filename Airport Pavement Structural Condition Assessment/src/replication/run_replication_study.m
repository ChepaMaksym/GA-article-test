function report = run_replication_study()
% Run paper-style replication checks from the bundled article data.
projectRoot = find_project_root();
sandboxDir = fullfile(projectRoot, 'sandbox');
resultsDir = fullfile(sandboxDir, 'results');
if ~exist(resultsDir, 'dir')
    mkdir(resultsDir);
end

xmlPath = fullfile(projectRoot, ...
    'Using Genetic Algorithms to Improve Airport Pavement Structural Condition Assessment Code Development and Case Study.xml');

direct = article_tables1_2_direct_validation();
indirect = article_table3_indirect_validation_input();
caseStudy = article_table5_case_study_input();
caseDeflections = article_case_study_reported_deflections();
table4 = article_table4_indirect_ga_results();
table6 = article_table6_case_study_ga_results();
table7 = article_table7_software_comparison();
consistency = verify_article_data_consistency(xmlPath);
gaSurrogate = run_ga_surrogate_backcalculation();

directDiff = direct.matlab_mm - direct.kenpave_mm;
directAbsDiff = abs(directDiff);
directPctDiff = 100 * directAbsDiff ./ direct.kenpave_mm;

bestIndirect = table4(5);
indirectTrue = indirect.E_MPa;
indirectEstimated = [bestIndirect.E1_MPa, bestIndirect.E2_MPa];
indirectAbsError = abs(indirectEstimated - indirectTrue);
indirectPctError = 100 * indirectAbsError ./ indirectTrue;

caseResidualMm = caseDeflections.calculated_mm - caseStudy.D_mm;
caseSseMm2 = sum(caseResidualMm.^2);
caseSseM2 = sum((caseResidualMm / 1000).^2);
caseMaxAbsMm = max(abs(caseResidualMm));
caseMeanAbsMm = mean(abs(caseResidualMm));

comparisonRecomputed = zeros(numel(table7), 2);
comparisonReported = zeros(numel(table7), 2);
for i = 1:numel(table7)
    row = table7(i);
    comparisonRecomputed(i, 1) = 100 * abs(row.software_ga_MPa - row.backgenetic3d_MPa) / row.backgenetic3d_MPa;
    comparisonRecomputed(i, 2) = 100 * abs(row.software_ga_MPa - row.elmod_MPa) / row.elmod_MPa;
    comparisonReported(i, :) = [row.error_vs_backgenetic3d_pct, row.error_vs_elmod_pct];
end
comparisonRounded = round(comparisonRecomputed, 1);

report = struct();
report.sandbox_dir = sandboxDir;
report.direct = struct( ...
    'pressure_kPa', direct.pressure_kPa, ...
    'max_abs_diff_mm', max(directAbsDiff), ...
    'max_pct_diff', max(directPctDiff), ...
    'mean_abs_diff_mm', mean(directAbsDiff), ...
    'diff_mm', directDiff, ...
    'pct_diff', directPctDiff);
report.indirect = struct( ...
    'true_MPa', indirectTrue, ...
    'estimated_MPa', indirectEstimated, ...
    'abs_error_MPa', indirectAbsError, ...
    'pct_error', indirectPctError);
report.case_study = struct( ...
    'measured_mm', caseStudy.D_mm, ...
    'reported_calculated_mm', caseDeflections.calculated_mm, ...
    'residual_mm', caseResidualMm, ...
    'sse_mm2', caseSseMm2, ...
    'sse_m2', caseSseM2, ...
    'reported_fitness', caseDeflections.reported_fitness, ...
    'fitness_gap_m2', caseSseM2 - caseDeflections.reported_fitness, ...
    'max_abs_residual_mm', caseMaxAbsMm, ...
    'mean_abs_residual_mm', caseMeanAbsMm);
report.table7 = struct( ...
    'recomputed_pct', comparisonRecomputed, ...
    'recomputed_rounded_pct', comparisonRounded, ...
    'reported_pct', comparisonReported);
report.ga_surrogate = gaSurrogate;
report.progress = struct( ...
    'article_constants_encoded', true, ...
    'direct_check_replicated_from_reported_outputs', true, ...
    'indirect_check_replicated_from_reported_outputs', true, ...
    'case_study_replicated_from_reported_outputs', true, ...
    'ga_surrogate_executable', true, ...
    'full_mlet_forward_solver_executable', false, ...
    'full_ga_backcalculation_executable', false);
report.issues = replication_issues(consistency, report);

write_replication_report(report, resultsDir);
save(fullfile(resultsDir, 'replication_report.mat'), 'report');

fprintf('Replication sandbox: %s\n', sandboxDir);
fprintf('Direct check max MATLAB-vs-KENPAVE difference: %.4f mm (%.2f%%)\n', ...
    report.direct.max_abs_diff_mm, report.direct.max_pct_diff);
fprintf('Indirect check best moduli errors: E1 %.3f%%, E2 %.3f%%\n', ...
    report.indirect.pct_error(1), report.indirect.pct_error(2));
fprintf('Case-study basin max residual: %.4f mm; SSE %.3g m^2 vs reported %.3g\n', ...
    report.case_study.max_abs_residual_mm, report.case_study.sse_m2, report.case_study.reported_fitness);
fprintf('Report written to: %s\n', fullfile(resultsDir, 'replication_report.md'));
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

function issues = replication_issues(consistency, report)
issues = {};
for i = 1:numel(consistency.warnings)
    issues{end+1} = consistency.warnings{i}; %#ok<AGROW>
end

if abs(report.case_study.fitness_gap_m2) > 5e-11
    issues{end+1} = ['The rounded Section 6 calculated deflections give SSE = ' ...
        sprintf('%.3g', report.case_study.sse_m2) ' m^2, not exactly the reported Table 6 fitness ' ...
        sprintf('%.3g', report.case_study.reported_fitness) '. This is likely rounding of printed deflections.'];
end

if ~report.progress.full_mlet_forward_solver_executable
    issues{end+1} = ['The bundled project still does not contain a clean executable MATLAB MLET forward solver; ' ...
        'Appendix A is available only as raw XML/MathML extraction.'];
end

if any(abs(report.table7.recomputed_rounded_pct(:) - report.table7.reported_pct(:)) > 0.05)
    issues{end+1} = ['Some Table 7 percentage errors do not match normal one-decimal rounding of the table values. ' ...
        'The reported values appear to be truncated or rounded from hidden precision.'];
end

if max(report.ga_surrogate.paper_E_error_pct) > 10
    issues{end+1} = ['The executable GA sandbox uses a surrogate forward model and therefore does not reproduce ' ...
        'the Table 6 moduli exactly. This confirms that the true Appendix A MLET forward model is still required ' ...
        'for a full replication study.'];
end

if ~report.progress.full_ga_backcalculation_executable
    issues{end+1} = ['The GA optimization path is not independently rerunnable yet; current checks compare reported ' ...
        'article outputs and internal consistency, not a fresh optimization result.'];
end
end

function write_replication_report(report, resultsDir)
outPath = fullfile(resultsDir, 'replication_report.md');
fid = fopen(outPath, 'w');
if fid == -1
    error('Cannot open replication report for writing: %s', outPath);
end
cleanupObj = onCleanup(@() fclose(fid)); %#ok<NASGU>

fprintf(fid, '# Replication Sandbox Report\n\n');
fprintf(fid, 'Generated by `run_replication_study.m` from the bundled XML article and MATLAB data files.\n\n');

fprintf(fid, '## Progress\n');
fprintf(fid, '- Article constants encoded in MATLAB: yes\n');
fprintf(fid, '- Direct validation check from Tables 1 and 2: replicated from reported outputs\n');
fprintf(fid, '- Indirect GA check from Tables 3 and 4: replicated from reported outputs\n');
fprintf(fid, '- Airport case study from Tables 5, 6, and 7: replicated from reported outputs\n');
fprintf(fid, '- Executable GA sandbox with surrogate response model: yes\n');
fprintf(fid, '- Independent executable MLET forward solver: not yet available\n');
fprintf(fid, '- Independent executable GA back-calculation: not yet available\n\n');

fprintf(fid, '## Paper-Style Checks\n');
fprintf(fid, '- Direct check load pressure: %.3f kPa, matching the paper statement of about 550 kPa.\n', report.direct.pressure_kPa);
fprintf(fid, '- Direct check MATLAB vs KENPAVE max difference: %.4f mm (%.2f%%), mean difference: %.4f mm.\n', ...
    report.direct.max_abs_diff_mm, report.direct.max_pct_diff, report.direct.mean_abs_diff_mm);
fprintf(fid, '- Indirect check best moduli: estimated E1 = %.3f MPa and E2 = %.3f MPa versus true E1 = %.3f MPa and E2 = %.3f MPa.\n', ...
    report.indirect.estimated_MPa(1), report.indirect.estimated_MPa(2), report.indirect.true_MPa(1), report.indirect.true_MPa(2));
fprintf(fid, '- Indirect check percent errors: E1 = %.3f%%, E2 = %.3f%%.\n', ...
    report.indirect.pct_error(1), report.indirect.pct_error(2));
fprintf(fid, '- Case-study max residual between reported calculated and measured basin: %.4f mm; mean absolute residual: %.4f mm.\n', ...
    report.case_study.max_abs_residual_mm, report.case_study.mean_abs_residual_mm);
fprintf(fid, '- Case-study SSE from rounded deflections: %.6g mm^2, or %.6g m^2. Reported fitness: %.6g.\n\n', ...
    report.case_study.sse_mm2, report.case_study.sse_m2, report.case_study.reported_fitness);

fprintf(fid, '## Executable GA Surrogate Sandbox\n');
fprintf(fid, '- Optimizer used: `%s`\n', report.ga_surrogate.method);
fprintf(fid, '- GA best E: `[%.3f %.3f %.3f]` MPa\n', report.ga_surrogate.best_E_MPa);
fprintf(fid, '- Paper Table 6 analysis (5) E: `[%.3f %.3f %.3f]` MPa\n', report.ga_surrogate.paper_E_MPa);
fprintf(fid, '- Error vs paper E: `[%.3f %.3f %.3f]` %%\n', report.ga_surrogate.paper_E_error_pct);
fprintf(fid, '- GA sandbox fitness: `%.6g`; paper reported fitness: `%.6g`\n', ...
    report.ga_surrogate.best_fitness, report.ga_surrogate.paper_fitness);
fprintf(fid, '- GA sandbox max residual: `%.4f mm`\n', report.ga_surrogate.max_abs_residual_mm);
fprintf(fid, '- Limitation: this uses the calibrated surrogate in `surrogate_case_study_forward.m`, not the article Appendix A MLET solver.\n\n');

fprintf(fid, '## Table 7 Error Recalculation\n');
fprintf(fid, '| Modulus | Recomputed vs BackGenetic3D | Reported vs BackGenetic3D | Recomputed vs ELMOD | Reported vs ELMOD |\n');
fprintf(fid, '|---|---:|---:|---:|---:|\n');
names = {'E1', 'E2', 'E3'};
for i = 1:numel(names)
    fprintf(fid, '| %s | %.1f%% | %.1f%% | %.1f%% | %.1f%% |\n', names{i}, ...
        report.table7.recomputed_rounded_pct(i, 1), report.table7.reported_pct(i, 1), ...
        report.table7.recomputed_rounded_pct(i, 2), report.table7.reported_pct(i, 2));
end
fprintf(fid, '\n');

fprintf(fid, '## Issues Blocking Full Reproduction\n');
for i = 1:numel(report.issues)
    fprintf(fid, '- %s\n', report.issues{i});
end
end
