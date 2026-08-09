function report = eu2614_verify_fixture()
% Independently verify the committed JSON/CSV endpoint fixture.

    here = fileparts(mfilename('fullpath'));
    candidate_root = fileparts(fileparts(here));
    json_path = fullfile(candidate_root, 'fixtures', 'frozen_endpoint.json');
    csv_path = fullfile(candidate_root, 'fixtures', 'run0_cycles.csv');

    fixture = jsondecode(fileread(json_path));
    assert(strcmp(fixture.candidate_id, 'EU26-14'));
    assert(strcmp(fixture.status, 'TARGETED_ARTIFACT_REPLAY_ONLY'));
    assert(strcmp(fixture.paper_mapping, 'PAPER_CONTEXT_ONLY'));
    assert(strcmp(fixture.result_archive_sha256, ...
        '22c0468ce1d01e03c30826abcd0952942a5d03d7822c0cc509897c6f7a40540e'));
    assert(strcmp(fixture.member.sha256, ...
        '310f68adb1878ea8179c527e42831286b472ec8dc1bd96984c843b9e5f7d344b'));
    assert(fixture.member.tar_data_offset == 481445376);
    assert(fixture.member.bytes == 462408);

    seeds = reshape(double(fixture.endpoint.seeds), 1, []);
    assert(isequal(seeds, 0:50));
    assert(fixture.endpoint.dimension == 15);
    assert(fixture.endpoint.budget == 3000000);
    assert(fixture.endpoint.n_runs == 51);
    assert(strcmp(fixture.run0.error, '0.0'));
    assert(isequal(reshape(double(fixture.run0.improvements_shape), 1, []), [339, 2]));
    assert(str2double(fixture.run0.first_improvement{1}) == 4096.0);
    assert(str2double(fixture.run0.first_improvement{2}) == 17928356740.02234);
    assert(str2double(fixture.run0.last_improvement{1}) == 2882691.0);
    assert(str2double(fixture.run0.last_improvement{2}) == 9.243294130101276e-09);
    assert(str2double(fixture.run0.pre_refine_error) == 0.8729793091438722);
    assert(fixture.run0.nfev_pre_refine == 2876679);
    assert(fixture.run0.nfev_total == 2893419);
    assert(fixture.stop_semantic_conflict.unspent_evaluations == 106581);
    assert(fixture.stop_semantic_conflict.budget_exhaustion_claim_forbidden);

    handle = fopen(csv_path, 'r');
    assert(handle >= 0);
    cleanup = onCleanup(@() fclose(handle)); %#ok<NASGU>
    header = fgetl(handle);
    expected_header = ['cycle,mode,nfev_start,nfev_end,nfev_delta,' ...
        'best_f_start,best_f_end,improvement,nfev_phase0,' ...
        'n_basins_phase0,phi_used,sampling_method,sample_reused'];
    assert(strcmp(header, expected_header));

    rows = {};
    while true
        line = fgetl(handle);
        if ~ischar(line)
            break;
        end
        fields = strsplit(line, ',');
        assert(numel(fields) == 13);
        rows{end + 1} = fields; %#ok<AGROW>
    end
    assert(numel(rows) == 30);

    prior_end = 0;
    reused_count = 0;
    zero_eval_reused_count = 0;
    for index = 1:numel(rows)
        fields = rows{index};
        cycle = str2double(fields{1});
        mode = fields{2};
        nfev_start = str2double(fields{3});
        nfev_end = str2double(fields{4});
        nfev_delta = str2double(fields{5});
        best_start = str2double(fields{6});
        best_end = str2double(fields{7});
        improvement = str2double(fields{8});
        nfev_phase0 = str2double(fields{9});
        sample_reused = strcmp(fields{13}, 'true');

        assert(cycle == index - 1);
        assert(nfev_start == prior_end);
        assert(nfev_delta == nfev_end - nfev_start);
        if mod(cycle, 2) == 0
            assert(strcmp(mode, 'alt-0'));
            assert(nfev_phase0 == 4096);
            assert(~sample_reused);
        else
            assert(strcmp(mode, 'alt-1'));
            assert(nfev_phase0 == 0);
            assert(sample_reused);
            reused_count = reused_count + 1;
        end
        if cycle == 0
            assert(isinf(best_start));
            assert(isinf(improvement));
        else
            assert(improvement == best_start - best_end);
        end
        if nfev_delta == 0
            assert(sample_reused);
            assert(str2double(fields{10}) == 0);
            assert(improvement == 0);
            zero_eval_reused_count = zero_eval_reused_count + 1;
        end
        prior_end = nfev_end;
    end
    assert(prior_end == 2876679);
    assert(reused_count == 15);
    assert(zero_eval_reused_count == 1);

    report = struct();
    report.schema_version = '1.0.0';
    report.candidate_id = 'EU26-14';
    report.status = 'TARGETED_ARTIFACT_REPLAY_ONLY';
    report.paper_mapping = 'PAPER_CONTEXT_ONLY';
    report.cross_language_gate = 'PASS_CROSS_LANGUAGE_CONTROLS';
    report.seed_count = 51;
    report.cycle_count = 30;
    report.reused_cycle_count = reused_count;
    report.zero_eval_reused_cycle_count = zero_eval_reused_count;
    report.final_cycle_nfev = prior_end;
    report.run0_nfev_total = fixture.run0.nfev_total;
    report.unspent_evaluations = fixture.stop_semantic_conflict.unspent_evaluations;
    report.assertions = 31;
end
