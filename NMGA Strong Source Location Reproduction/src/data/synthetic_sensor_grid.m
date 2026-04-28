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
    case 'few_sensors'
        x = sourceX + [35, 65, 95, 130, 165, 210];
        y = sourceY + [0, 15, -15, 20, -20, 0];
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
