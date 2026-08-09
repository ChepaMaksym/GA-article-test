function run_matlab_tests()
% Parse the authenticated point set and evaluate EU26-11 independently.

point_path = getenv('EU2611_POINT_SET');
report_path = getenv('EU2611_OCTAVE_REPORT');
if isempty(point_path) || isempty(report_path)
    error('EU2611:Environment', 'EU2611_POINT_SET and EU2611_OCTAVE_REPORT are required.');
end
if exist(report_path, 'file') || exist(report_path, 'dir')
    error('EU2611:OutputExists', 'Report path must be new.');
end

closed_form = eu2611_l2_star(0.5);
assert(abs(closed_form - sqrt(1.0 / 12.0)) <= 1e-15);

expected_header = 'n=150,k=128,dim=20, discrepancy=0.224604, runtime=174.924370';
handle = fopen(point_path, 'r');
if handle < 0
    error('EU2611:Open', 'Cannot open the point-set member.');
end
cleanup = onCleanup(@() fclose(handle));
header = fgetl(handle);
assert(ischar(header));
assert(strcmp(header, expected_header));

rows = 128;
dimension = 20;
points = zeros(rows, dimension);
for row = 1:rows
    line = fgetl(handle);
    assert(ischar(line));
    assert(numel(line) == dimension * 9);
    for axis = 1:dimension
        offset = (axis - 1) * 9;
        token = line(offset + 1:offset + 8);
        separator = line(offset + 9);
        assert(separator == ' ');
        assert(~isempty(regexp(token, '^(0|1)\.[0-9]{6}$', 'once')));
        value = str2double(token);
        assert(isfinite(value) && value >= 0.0 && value <= 1.0);
        points(row, axis) = value;
    end
end
assert(fgetl(handle) == -1);
clear cleanup;

l2_star = eu2611_l2_star(points);
log_value = log10(l2_star);
paper_display = sprintf('%.2f', log_value);
assert(abs(l2_star - 6.892638555983242e-05) <= 5e-16);
assert(abs(log_value - (-4.1616144949364955)) <= 1e-10);
assert(strcmp(paper_display, '-4.16'));

output = fopen(report_path, 'w');
if output < 0
    error('EU2611:ReportOpen', 'Cannot create the Octave report.');
end
output_cleanup = onCleanup(@() fclose(output));
fprintf(output, ['{"candidate_id":"EU26-11","status":"PASS_OCTAVE_FORMULA",' ...
    '"l2_star":%.17g,"log10_l2_star":%.17g,' ...
    '"display_two_decimals":"%s","assertions":14}\n'], ...
    l2_star, log_value, paper_display);
clear output_cleanup;
fprintf('EU26-11 Octave formula assertions passed.\n');
end
