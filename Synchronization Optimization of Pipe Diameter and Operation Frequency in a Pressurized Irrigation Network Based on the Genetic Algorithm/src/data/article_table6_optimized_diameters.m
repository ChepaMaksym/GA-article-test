function data = article_table6_optimized_diameters()
% Table 6. Optimized branch pipe diameters, mm. NaN represents "-".
data.segment_number = 1:7;
data.branch_number = (1:10).';
data.PDM = [
    200 200 200 200 200 200 200
    250 250 250 250 250 315 NaN
    315 315 315 315 315 315 315
    160 200 200 200 315 315 NaN
    200 200 200 200 200 200 250
    200 250 250 250 315 315 NaN
    200 200 250 250 315 315 315
    160 200 200 200 200 200 NaN
    315 315 315 315 315 315 315
    160 160 160 200 NaN NaN NaN
];
data.SOM = [
    200 200 200 200 250 250 315
    160 160 200 200 200 200 NaN
    160 160 160 200 250 250 315
    200 200 250 250 250 250 NaN
    200 200 200 315 315 315 315
    160 160 200 200 200 250 NaN
    160 160 160 160 250 250 2
    160 160 160 160 160 160 NaN
    160 160 200 250 315 315 315
    200 200 200 200 NaN NaN NaN
];
data.notes = 'The XML table reports a value of 2 for SOM branch 7 segment 7; this is preserved and flagged as a source anomaly.';
end
