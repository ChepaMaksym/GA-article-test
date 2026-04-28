function data = article_table2_original_branch_diameters()
% Table 2. Original branch pipe segment diameters, mm. NaN represents "-".
data.segment_number = 1:7;
data.branch_number = (1:10).';
data.diameter_mm = [
    160 200 250 250 315 315 315
    160 200 250 250 315 315 NaN
    160 200 250 250 315 315 315
    160 200 250 250 315 315 NaN
    160 200 250 250 315 315 315
    160 200 250 250 315 315 NaN
    160 200 250 250 315 315 315
    160 200 250 250 315 315 NaN
    160 200 250 250 315 315 315
    160 200 250 250 NaN NaN NaN
];
end
