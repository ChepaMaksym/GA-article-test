function deflection_mm = surrogate_case_study_forward(E_MPa)
% Surrogate response surface anchored to the paper's reported case-study result.
% This is a GA test stand, not a replacement for the Appendix A MLET solver.
E_ref = [5850.679, 3615.922, 208.747];
d_ref_mm = [0.4853, 0.4020, 0.3666, 0.3262, 0.2309, 0.1841, 0.1487, 0.1222];

sensitivity = [
    0.35, 0.25, 0.15
    0.33, 0.27, 0.18
    0.30, 0.28, 0.20
    0.26, 0.30, 0.23
    0.18, 0.32, 0.30
    0.14, 0.31, 0.34
    0.10, 0.28, 0.38
    0.08, 0.24, 0.42
];

scale = exp(-sensitivity * log(E_MPa(:) ./ E_ref(:)));
deflection_mm = d_ref_mm .* scale.';
end
