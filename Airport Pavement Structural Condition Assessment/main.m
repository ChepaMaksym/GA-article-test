projectRoot = fileparts(mfilename('fullpath'));
addpath(genpath(fullfile(projectRoot, 'src')));

xmlPath = fullfile(projectRoot, ...
    'Using Genetic Algorithms to Improve Airport Pavement Structural Condition Assessment Code Development and Case Study.xml');
appendixDir = fullfile(projectRoot, 'appendix');
resultsDir = fullfile(projectRoot, 'results');
appendixOut = fullfile(appendixDir, 'appendix_a_raw.xml');

if ~exist(appendixDir, 'dir')
    mkdir(appendixDir);
end
if ~exist(resultsDir, 'dir')
    mkdir(resultsDir);
end

caseStudy = article_table5_case_study_input();
table4 = article_table4_indirect_ga_results();
table6 = article_table6_case_study_ga_results();
table7 = article_table7_software_comparison();
report = verify_article_data_consistency(xmlPath);
gaResult = run_ga_surrogate_backcalculation();

fprintf('Article: Using Genetic Algorithms to Improve Airport Pavement Structural Condition Assessment\n');
fprintf('DOI: 10.3390/info14050286\n\n');

fprintf('Table 5 case-study input\n');
fprintf('h = [%g, %g, %s]\n', caseStudy.h(1), caseStudy.h(2), 'Inf');
fprintf('nu = [%g, %g, %g]\n', caseStudy.nu(1), caseStudy.nu(2), caseStudy.nu(3));
fprintf('F = %.1f kN, a = %.2f m\n', caseStudy.F_kN, caseStudy.a_m);
fprintf('r = [%s] m\n', strjoin(compose('%.2f', caseStudy.r_m), ', '));
fprintf('D = [%s] mm\n\n', strjoin(compose('%.3f', caseStudy.D_mm), ', '));

fprintf('Table 4 reported GA results\n');
for i = 1:numel(table4)
    row = table4(i);
    fprintf(['(%d) P=%d, crossover=%.2f, mutation=%.2f, E1=[%g %g], E2=[%g %g], ' ...
        'calc=[%.3f %.3f], fitness=%s\n'], ...
        row.analysis_id, row.population, row.crossover_probability, row.mutation_probability, ...
        row.E1_range_MPa(1), row.E1_range_MPa(2), row.E2_range_MPa(1), row.E2_range_MPa(2), ...
        row.E1_MPa, row.E2_MPa, row.fitness_text);
end
fprintf('\n');

fprintf('Table 6 case-study GA back-calculation results\n');
for i = 1:numel(table6)
    row = table6(i);
    fprintf(['(%d) P=%d, crossover=%.2f, mutation=%.2f, E1=[%g %g], E2=[%g %g], E3=[%g %g], ' ...
        'calc=[%.3f %.3f %.3f], fitness=%s\n'], ...
        row.analysis_id, row.population, row.crossover_probability, row.mutation_probability, ...
        row.E1_range_MPa(1), row.E1_range_MPa(2), row.E2_range_MPa(1), row.E2_range_MPa(2), ...
        row.E3_range_MPa(1), row.E3_range_MPa(2), row.E1_MPa, row.E2_MPa, row.E3_MPa, row.fitness_text);
end
fprintf('\n');

fprintf('Table 7 moduli comparison\n');
for i = 1:numel(table7)
    row = table7(i);
    fprintf('%s: BackGenetic3D=%.3f, ELMOD=%.1f, Software GA=%.3f, errors=[%.1f%%, %.1f%%]\n', ...
        row.name, row.backgenetic3d_MPa, row.elmod_MPa, row.software_ga_MPa, ...
        row.error_vs_backgenetic3d_pct, row.error_vs_elmod_pct);
end
fprintf('\n');

fprintf('Live GA sandbox result\n');
fprintf('method = %s\n', gaResult.method);
fprintf('best E = [%.3f, %.3f, %.3f] MPa\n', gaResult.best_E_MPa);
fprintf('fitness = %.6g\n', gaResult.best_fitness);
fprintf('max residual = %.4f mm\n\n', gaResult.max_abs_residual_mm);

export_appendix_a_xml(xmlPath, appendixOut);
fprintf('Raw Appendix A extracted to: %s\n', appendixOut);
fprintf('Consistency checks: %d passed, %d warnings\n', report.pass_count, report.warning_count);
for i = 1:numel(report.warnings)
    fprintf('Warning: %s\n', report.warnings{i});
end
