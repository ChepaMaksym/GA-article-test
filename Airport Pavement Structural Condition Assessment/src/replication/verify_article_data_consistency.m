function report = verify_article_data_consistency(xmlPath)
% Verify that local MATLAB constants match the article-backed values.
xmlText = fileread(xmlPath);

caseStudy = article_table5_case_study_input();
table4 = article_table4_indirect_ga_results();
table6 = article_table6_case_study_ga_results();
table7 = article_table7_software_comparison();

checks = {};
warnings = {};

assert(all(abs(caseStudy.h(1:2) - [0.155, 0.22]) < 1e-12), 'Table 5 layer thickness values do not match the article.');
assert(isinf(caseStudy.h(3)), 'Table 5 third layer should be represented as Inf in MATLAB.');
assert(all(abs(caseStudy.nu - [0.35, 0.35, 0.45]) < 1e-12), 'Table 5 Poisson ratios do not match the article.');
assert(abs(caseStudy.F_kN - 164.2) < 1e-12, 'Table 5 load value does not match the article.');
assert(abs(caseStudy.a_m - 0.15) < 1e-12, 'Table 5 load radius does not match the article.');
assert(isequal(round(caseStudy.r_m, 12), round([0, 0.2, 0.3, 0.45, 0.9, 1.2, 1.5, 1.8], 12)), ...
    'Table 5 sensor locations do not match the article.');
assert(isequal(round(caseStudy.D_mm, 12), round([0.488, 0.396, 0.372, 0.327, 0.228, 0.180, 0.143, 0.112], 12)), ...
    'Table 5 measured deflections do not match the article.');
checks{end+1} = 'Table 5 constants match the article values.';

assert(numel(table4) == 5, 'Table 4 should contain five analyses.');
assert(abs(table4(5).E1_MPa - 2010.584) < 1e-12 && abs(table4(5).E2_MPa - 99.877) < 1e-12, ...
    'Table 4 best-analysis moduli do not match the article.');
checks{end+1} = 'Table 4 optimization results match the reported best-analysis values.';

assert(numel(table6) == 5, 'Table 6 should contain five analyses.');
assert(table6(5).population == 30, 'Table 6 analysis (5) should use population 30.');
assert(abs(table6(5).E1_MPa - 5850.679) < 1e-12 && ...
       abs(table6(5).E2_MPa - 3615.922) < 1e-12 && ...
       abs(table6(5).E3_MPa - 208.747) < 1e-12, ...
    'Table 6 final moduli do not match the article.');
checks{end+1} = 'Table 6 case-study back-calculation results are stored correctly.';

assert(numel(table7) == 3, 'Table 7 should contain three modulus rows.');
assert(abs(table7(1).software_ga_MPa - table6(5).E1_MPa) < 1e-12 && ...
       abs(table7(2).software_ga_MPa - table6(5).E2_MPa) < 1e-12 && ...
       abs(table7(3).software_ga_MPa - table6(5).E3_MPa) < 1e-12, ...
    'Table 7 Software GA values should match Table 6 analysis (5).');
checks{end+1} = 'Table 7 comparison values are internally consistent with Table 6.';

requiredSnippets = {
    '2010.584 '
    '99.877 '
    '164.2 kN'
    '0.15 m'
    '5850.679'
    '3615.922'
    '208.747'
    '5770.913'
    '5024.1'
};

for i = 1:numel(requiredSnippets)
    assert(contains(xmlText, requiredSnippets{i}), ...
        'XML article text is missing an expected numeric reference: %s', requiredSnippets{i});
end
checks{end+1} = 'The local XML article contains the key numeric references used by the project.';

if contains(xmlText, 'population is too small') && contains(xmlText, 'not less than 20')
    warnings{end+1} = ['The article discussion says the population should be "not less than 20", ' ...
        'but Table 6 analysis (4) uses population 5. The MATLAB data keeps both because that inconsistency is in the source article.'];
end

if contains(xmlText, 'E<sub>1</sub> = 5,850,679 MPa')
    warnings{end+1} = ['The prose in Section 6 prints case-study moduli with thousands separators as ' ...
        '"5,850,679 MPa", "3,615,922 MPa", and "208,747 MPa". Table 6 and Table 7 show the intended ' ...
        'decimal values 5850.679, 3615.922, and 208.747 MPa, which are the values stored in MATLAB.'];
end

report = struct();
report.pass_count = numel(checks);
report.warning_count = numel(warnings);
report.checks = checks;
report.warnings = warnings;
end
