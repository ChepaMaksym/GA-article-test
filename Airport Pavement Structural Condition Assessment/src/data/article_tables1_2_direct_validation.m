function data = article_tables1_2_direct_validation()
% Tables 1 and 2. Direct validation against KENPAVE.
data.h_m = [0.3, 0.5, Inf];
data.nu = [0.25, 0.30, 0.35];
data.E_MPa = [2000, 200, 100];
data.F_kN = 38.87;
data.a_m = 0.15;
data.r_m = [0, 0.2, 0.3, 0.6, 0.9, 1.0];
data.matlab_mm = [0.2779, 0.2215, 0.1981, 0.1499, 0.1166, 0.1079];
data.kenpave_mm = [0.2745, 0.2179, 0.1949, 0.1475, 0.1143, 0.1056];
data.pressure_kPa = data.F_kN / (pi * data.a_m^2);
end
