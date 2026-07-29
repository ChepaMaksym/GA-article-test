function rows = article_table5_model_performance()
% Table 5. Operating frequency, pump performance, and irrigation period.
rows = make_rows('PDM', [ ...
    1 50 844 11.2 81.6 5.1
    2 50 555 15.9 76.3 9.7
    3 50 626 14.9 79.4 8.3
    4 50 646 14.6 80.0 8.7
    5 50 673 14.2 80.7 6.1]);
rows = [rows, make_rows('OFM', [ ...
    1 42 593 9.6 79.0 8.4
    2 41 636 8.3 79.3 8.1
    3 45 727 9.6 80.4 7.1
    4 41 612 8.7 79.2 9.3
    5 44 644 10.2 75.5 7.6])];
rows = [rows, make_rows('SOM', [ ...
    1 50 579 15.6 77.5 8.6
    2 48 642 13.1 80.1 8.2
    3 43 581 10.4 78.8 8.2
    4 48 545 14.5 76.4 10.7
    5 43 593 12.3 79.0 6.5])];
end

function rows = make_rows(model, values)
for i = 1:size(values, 1)
    rows(i) = struct( ... %#ok<AGROW>
        'model', model, ...
        'sectoring', values(i, 1), ...
        'frequency_Hz', values(i, 2), ...
        'pump_flow_m3_h', values(i, 3), ...
        'pump_head_m', values(i, 4), ...
        'pump_efficiency_pct', values(i, 5), ...
        'irrigation_period_h', values(i, 6));
end
end
