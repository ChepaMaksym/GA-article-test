function data = article_table4_pump_coefficients()
% Table 4. Pump polynomial coefficients shown in the XML table.
% The article table has an ellipsis between 47 Hz and 42 Hz; only visible values are encoded.
data.frequency_Hz = [50 49 48 47 42 41];
data.has_ellipsis_gap = true;
data.B = [
    21.1, 20.26, 19.45, 18.64, 14.89, 14.19
    -0.004611, -0.004519, -0.004427, -0.004334, -0.003873, -0.003781
    -8.467e-6, -8.467e-6, -8.467e-6, -8.467e-6, -8.467e-6, -8.467e-6
    -1.329e-22, -4.025e-17, -7.911e-18, -1.066e-17, 3.556e-17, 7.502e-17
];
data.C = [
    -0.02273, 0.02265, -0.02257, 0.02248, 0.02206, 0.02197
    0.002277, 0.002316, 0.002356, 0.002397, 0.002632, 0.002685
    -1.919e-6, -1.919e-6, -2.068e-6, 2.149e-6, -2.64e-6, 2.758e-6
    3.97e-10, 4.203e-10, 4.455e-10, 4.729e-10, 6.493e-10, 6.95e-10
];
end
