function concentration = gaussian_plume_concentration(source, sensors, windSpeed_mps)
sourceX = source(1);
sourceY = source(2);
Q_gps = source(3);
H_m = source(4);

xDownwind = sensors.x_m - sourceX;
yCrosswind = sensors.y_m - sourceY;
z = sensors.z_m;

concentration = zeros(size(xDownwind));
valid = xDownwind > 0 & windSpeed_mps > 0 & Q_gps >= 0 & H_m >= 0;
if ~any(valid)
    return;
end

[sigmaY, sigmaZ] = pasquill_gifford_e(xDownwind(valid));
verticalTerm = exp(-((z(valid) - H_m) .^ 2) ./ (2 .* sigmaZ .^ 2)) ...
    + exp(-((z(valid) + H_m) .^ 2) ./ (2 .* sigmaZ .^ 2));
crossTerm = exp(-(yCrosswind(valid) .^ 2) ./ (2 .* sigmaY .^ 2));
denominator = 2 .* pi .* windSpeed_mps .* sigmaY .* sigmaZ;
concentration(valid) = Q_gps ./ denominator .* crossTerm .* verticalTerm;
concentration(~isfinite(concentration)) = 0;
end
