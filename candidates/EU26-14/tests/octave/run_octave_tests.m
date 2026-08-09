function report = run_octave_tests(output_path)
% Run EU26-14 independent controls and optionally create one JSON report.

    if nargin < 1
        output_path = '';
    end
    report = eu2614_verify_fixture();
    if ~isempty(output_path)
        if exist(output_path, 'file') || exist(output_path, 'dir')
            error('EU26-14:OutputExists', 'Output path already exists');
        end
        [handle, message] = fopen(output_path, 'x');
        if handle < 0
            error('EU26-14:OutputCreateFailed', '%s', message);
        end
        cleanup = onCleanup(@() fclose(handle)); %#ok<NASGU>
        count = fwrite(handle, [jsonencode(report), newline], 'char');
        assert(count > 0);
    end
    fprintf('%s\n', report.cross_language_gate);
end
