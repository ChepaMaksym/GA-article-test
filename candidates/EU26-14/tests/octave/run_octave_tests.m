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
        [handle, temporary_path, message] = mkstemp([output_path, '.tmp.XXXXXX']);
        if handle < 0
            error('EU26-14:OutputCreateFailed', '%s', message);
        end
        try
            count = fwrite(handle, [jsonencode(report), newline], 'char');
            assert(count > 0);
            if fclose(handle) ~= 0
                error('EU26-14:OutputCloseFailed', 'Cannot close temporary report');
            end
            handle = -1;
            [status, message] = link(temporary_path, output_path);
            if status ~= 0
                error('EU26-14:OutputCreateFailed', '%s', message);
            end
            unlink(temporary_path);
        catch failure
            if handle >= 0
                fclose(handle);
            end
            if exist(temporary_path, 'file')
                unlink(temporary_path);
            end
            rethrow(failure);
        end
    end
    fprintf('%s\n', report.cross_language_gate);
end
