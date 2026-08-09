function write_transition_results(fixture_path, output_path)
%WRITE_TRANSITION_RESULTS Emit independent Octave/MATLAB fixture results.

test_dir = fileparts(mfilename('fullpath'));
candidate_root = fileparts(fileparts(test_dir));
implementation_dir = fullfile(candidate_root, 'environments', 'matlab');
addpath(implementation_dir);
path_cleanup = onCleanup(@() rmpath(implementation_dir)); %#ok<NASGU>

if exist('jsondecode', 'builtin') == 0 && exist('jsondecode', 'file') == 0
    error('eu2617:MissingJsonDecode', 'jsondecode is required');
end
fixture = jsondecode(fileread(fixture_path));
file_id = fopen(output_path, 'w');
if file_id < 0
    error('eu2617:OutputFailure', 'could not open output TSV');
end
file_cleanup = onCleanup(@() fclose(file_id)); %#ok<NASGU>
fprintf(file_id, 'name\tgdm\tmutation_rate\tcrossover_rate\tbranch\n');
for index = 1:numel(fixture.cases)
    if iscell(fixture.cases)
        item = fixture.cases{index};
    else
        item = fixture.cases(index);
    end
    result = eu2617_transition(item.fitness, item.state, fixture.config);
    fprintf(file_id, '%s\t%.17g\t%.17g\t%.17g\t%s\n', ...
        item.name, result.gdm, result.current.mutation_rate, ...
        result.current.crossover_rate, result.branch);
end
end
