function f = surrogate_case_study_fitness(E_MPa)
% Article fitness form: sum of squared differences between calculated and measured deflections.
caseStudy = article_table5_case_study_input();
calculated_m = surrogate_case_study_forward(E_MPa) / 1000;
measured_m = caseStudy.D_mm / 1000;
f = sum((calculated_m - measured_m).^2);
end
