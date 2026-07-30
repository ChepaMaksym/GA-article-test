function sensors = synthetic_sensor_grid(layout)
if nargin < 1 || isempty(layout)
    layout = 'figure_eight';
end

article = article_reported();
sourceX = article.scenario.target_x_m;
sourceY = article.scenario.target_y_m;

switch lower(layout)
    case 'figure_eight'
        theta = linspace(0, 2 * pi, 17);
        theta(end) = [];
        loop1X = sourceX + 80 + 42 * cos(theta);
        loop1Y = sourceY + 22 * sin(theta);
        loop2X = sourceX + 155 + 42 * cos(theta);
        loop2Y = sourceY + 22 * sin(theta);
        x = [loop1X, loop2X, sourceX + [25, 50, 110, 190]];
        y = [loop1Y, loop2Y, sourceY + [0, 18, -18, 0]];
    case 'figure_eight_20'
        base = synthetic_sensor_grid('figure_eight');
        idx = round(linspace(1, numel(base.x_m), 20));
        x = base.x_m(idx)';
        y = base.y_m(idx)';
    case 'few_sensors'
        x = sourceX + [35, 65, 95, 130, 165, 210];
        y = sourceY + [0, 15, -15, 20, -20, 0];
    case 'sparse_10'
        x = sourceX + [30, 50, 70, 95, 120, 145, 170, 200, 225, 250];
        y = sourceY + [0, 18, -18, 24, -24, 12, -12, 28, -28, 0];
    case 'sparse_5'
        x = sourceX + [40, 80, 125, 175, 230];
        y = sourceY + [0, 22, -22, 16, -16];
    case 'sparse_3'
        x = sourceX + [55, 130, 220];
        y = sourceY + [0, 18, -18];
    case 'symmetric_poor'
        x = sourceX + [55, 85, 115, 145, 175, 205, 55, 85, 115, 145, 175, 205];
        y = sourceY + [18, 18, 18, 18, 18, 18, -18, -18, -18, -18, -18, -18];
    otherwise
        error('Unknown sensor layout: %s', layout);
end

sensors = struct();
sensors.layout = layout;
sensors.x_m = x(:);
sensors.y_m = y(:);
sensors.z_m = 1.5 * ones(numel(x), 1);
sensors.note = 'Synthetic dual-loop/figure-eight sensor grid; not original article coordinates.';
end
