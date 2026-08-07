function write_fixed_tape_report(output_path)
%WRITE_FIXED_TAPE_REPORT Emit the independent MATLAB/Octave fixture result.

if nargin ~= 1 || ~(ischar(output_path) || (isstring(output_path) && isscalar(output_path)))
    error('banditverify:InvalidOutput', 'One output path is required.');
end
implementation_dir = fileparts(mfilename('fullpath'));
candidate_root = fileparts(fileparts(implementation_dir));
fixture_path = fullfile(candidate_root, 'fixtures', 'fixed_controller_tape.json');
fixture = jsondecode(fileread(fixture_path));
report = bandit_run_fixed_tape(fixture);
encoded = jsonencode(report);
handle = fopen(char(output_path), 'w');
if handle < 0
    error('banditverify:OutputOpen', 'Could not open output path.');
end
cleanup = onCleanup(@() fclose(handle)); %#ok<NASGU>
fprintf(handle, '%s\n', encoded);
fprintf('Wrote synthetic fixed-tape report: %s\n', char(output_path));
end
