function data = article_table3_indirect_validation_input()
% Table 3 and Section 4.2. Two-layer indirect validation input.
data.h_m = [0.2, Inf];
data.nu = [0.25, 0.30];
data.E_MPa = [2000, 100];
data.F_kN = 50;
data.a_m = 0.15;
data.r_m = [0, 0.2, 0.3, 0.6, 0.9, 1.0];
data.kenpave_deflection_mm = [0.5565, 0.4478, 0.3871, 0.25, 0.1682, 0.1497];
end
