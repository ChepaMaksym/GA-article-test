function analysis = analyze_historical_runtime()
%ANALYZE_HISTORICAL_RUNTIME Estimate staged USA-001 qualification time.
% The estimate uses retained elapsed times and assumes the 100000-generation
% straggler's first 2000 generations scale linearly. It is not a benchmark.

verificationRoot = fileparts(mfilename("fullpath"));
workspace = fileparts(verificationRoot);
evidence = fullfile(workspace, "failure_logs", "USA-001_evidence");
evidenceReport = verify_retained_evidence(false);

definitions = [ ...
    runtime_definition("Primary", "primary_Runs_Raw.csv"); ...
    runtime_definition("Q1", "Q1_Runs_Raw_DIAGNOSTIC_ONLY.csv"); ...
    runtime_definition("Q2", "Q2_Runs_Raw_DIAGNOSTIC_ONLY.csv"); ...
    runtime_definition("Q3", "Q3_Runs_Raw_DIAGNOSTIC_ONLY.csv")];

Profile = strings(numel(definitions), 1);
HistoricalSeconds = zeros(numel(definitions), 1);
FailFastSerialSeconds = zeros(numel(definitions), 1);
TheoreticalBarrierLowerBoundSeconds = zeros(numel(definitions), 1);
ProjectedLPTFourWorkerSeconds = zeros(numel(definitions), 1);
IdealizedHistoricalToLPTSpeedup = zeros(numel(definitions), 1);

for index = 1:numel(definitions)
    runs = readtable(fullfile(evidence, definitions(index).runFile), ...
        "TextType", "string", "VariableNamingRule", "preserve");
    elapsed = numeric_column(runs, "ElapsedSeconds");
    iterations = numeric_column(runs, "ReportedIteration");
    longRuns = find(iterations == 100000);
    if height(runs) ~= 10 || any(~isfinite(elapsed) | elapsed <= 0) || ...
            any(~isfinite(iterations) | iterations < 0 | ...
            iterations ~= fix(iterations)) || numel(longRuns) ~= 1
        error("fastverify:UnexpectedHistoricalLedger", ...
            "%s has no single expected 100000-generation straggler.", ...
            definitions(index).name);
    end
    longIndex = longRuns(1);

    firstThousandEstimate = elapsed(longIndex) / 100;
    stageOneTimes = elapsed;
    stageOneTimes(longIndex) = firstThousandEstimate;
    serialFailFast = sum(stageOneTimes) + firstThousandEstimate;
    barrierStageOne = max(sum(stageOneTimes) / 4, max(stageOneTimes));
    barrierFailFast = barrierStageOne + firstThousandEstimate;
    projectedLPTStageOne = longest_processing_time(stageOneTimes, 4);
    projectedLPTFailFast = projectedLPTStageOne + firstThousandEstimate;

    Profile(index) = definitions(index).name;
    HistoricalSeconds(index) = sum(elapsed);
    FailFastSerialSeconds(index) = serialFailFast;
    TheoreticalBarrierLowerBoundSeconds(index) = barrierFailFast;
    ProjectedLPTFourWorkerSeconds(index) = projectedLPTFailFast;
    IdealizedHistoricalToLPTSpeedup(index) = ...
        sum(elapsed) / projectedLPTFailFast;
end

ByProfile = table(Profile, HistoricalSeconds, FailFastSerialSeconds, ...
    TheoreticalBarrierLowerBoundSeconds, ProjectedLPTFourWorkerSeconds, ...
    IdealizedHistoricalToLPTSpeedup);
pc = fastverify.pc_profile();
totalHistorical = sum(HistoricalSeconds);
totalFailFastSerial = sum(FailFastSerialSeconds);
totalBarrierLowerBound = sum(TheoreticalBarrierLowerBoundSeconds);
totalProjectedLPT = sum(ProjectedLPTFourWorkerSeconds);
empiricalComputeEstimate = max(totalProjectedLPT, ...
    totalFailFastSerial / pc.processBenchmarkFourWorkerSpeedup);

analysis = struct();
analysis.byProfile = ByProfile;
analysis.evidenceManifestSHA256 = ...
    evidenceReport.evidenceManifestSHA256;
analysis.historicalMinutes = totalHistorical / 60;
analysis.failFastSerialMinutes = totalFailFastSerial / 60;
analysis.theoreticalBarrierLowerBoundMinutes = ...
    totalBarrierLowerBound / 60;
analysis.projectedLPTFourWorkerMinutes = totalProjectedLPT / 60;
analysis.empiricalFourWorkerComputeMinutes = empiricalComputeEstimate / 60;
analysis.realisticEndToEndMinutes = [7, 9];
analysis.assumption = [ ...
    "Qualification stops only after an irreversible published gate fails; " ...
    "the 100000-generation run is linearly projected to generation 2000."];

disp(ByProfile);
fprintf("Historical algorithm time: %.1f min\n", analysis.historicalMinutes);
fprintf("Fail-fast serial estimate: %.1f min\n", analysis.failFastSerialMinutes);
fprintf("Four-worker theoretical barrier lower bound: %.1f min\n", ...
    analysis.theoreticalBarrierLowerBoundMinutes);
fprintf("Four-worker greedy-LPT projected makespan: %.1f min\n", ...
    analysis.projectedLPTFourWorkerMinutes);
fprintf("Four-worker empirical compute estimate: %.1f min\n", ...
    analysis.empiricalFourWorkerComputeMinutes);
fprintf("Realistic end-to-end estimate: %.0f-%.0f min\n", ...
    analysis.realisticEndToEndMinutes);
end

function definition = runtime_definition(name, file)
definition = struct("name", string(name), "runFile", string(file));
end

function duration = longest_processing_time(times, workers)
loads = zeros(workers, 1);
times = sort(times(:), "descend");
for index = 1:numel(times)
    [~, worker] = min(loads);
    loads(worker) = loads(worker) + times(index);
end
duration = max(loads);
end

function values = numeric_column(tableValue, name)
column = tableValue.(char(name));
if isnumeric(column) || islogical(column)
    values = double(column);
else
    values = str2double(string(column));
end
values = values(:);
end
