function report = verify_retained_evidence(verbose)
%VERIFY_RETAINED_EVIDENCE Validate compact USA-001 evidence without a rerun.

if nargin < 1
    verbose = true;
end
if ~islogical(verbose) || ~isscalar(verbose)
    error("fastverify:InvalidVerboseFlag", ...
        "verbose must be a logical scalar.");
end
started = tic;
verificationRoot = fileparts(mfilename("fullpath"));
workspace = fileparts(verificationRoot);
evidence = fullfile(workspace, "failure_logs", "USA-001_evidence");
manifestPath = fullfile(evidence, "evidence_manifest.csv");
expectedManifestHash = ...
    "1ded599074afc64d21a5092072f4a40633d1e3bc192d3fa44e40442d8c1f3b5e";

if fastverify.sha256_file(manifestPath) ~= expectedManifestHash
    error("fastverify:EvidenceManifestChanged", ...
        "The retained evidence manifest SHA-256 has changed.");
end

manifest = readtable(manifestPath, "TextType", "string", ...
    "VariableNamingRule", "preserve");
requiredManifest = ["File", "Length", "SHA256"];
if height(manifest) ~= 25 || ...
        ~all(ismember(requiredManifest, string(manifest.Properties.VariableNames)))
    error("fastverify:InvalidEvidenceManifest", ...
        "Evidence manifest schema or row count is invalid.");
end
manifestLengths = numeric_column(manifest, "Length");
manifestHashes = lower(string(manifest.SHA256));
manifestFiles = string(manifest.File);
if any(~isfinite(manifestLengths) | manifestLengths < 0 | ...
        manifestLengths ~= fix(manifestLengths)) || ...
        any(strlength(manifestFiles) == 0) || ...
        numel(unique(manifestFiles)) ~= height(manifest) || ...
        any(strlength(manifestHashes) ~= 64) || ...
        any(cellfun(@isempty, regexp(cellstr(manifestHashes), ...
        "^[0-9a-f]{64}$", "once")))
    error("fastverify:InvalidEvidenceManifest", ...
        "Evidence manifest contains invalid paths, lengths, or hashes.");
end
for row = 1:height(manifest)
    path = fullfile(evidence, char(manifest.File(row)));
    if ~isfile(path)
        error("fastverify:MissingEvidenceFile", ...
            "Missing evidence file: %s", path);
    end
    info = dir(path);
    if info.bytes ~= manifestLengths(row)
        error("fastverify:EvidenceLengthMismatch", ...
            "Evidence length mismatch: %s", path);
    end
    if fastverify.sha256_file(path) ~= manifestHashes(row)
        error("fastverify:EvidenceHashMismatch", ...
            "Evidence SHA-256 mismatch: %s", path);
    end
end

definitions = [ ...
    profile_definition("Primary", "primary_Runs_Raw.csv", ...
        "primary_Published_vs_Reproduced.csv", "FinalObjective"); ...
    profile_definition("Q1", "Q1_Runs_Raw_DIAGNOSTIC_ONLY.csv", ...
        "Q1_Published_vs_Diagnostic_Reproduced.csv", "FinalPaperObjective"); ...
    profile_definition("Q2", "Q2_Runs_Raw_DIAGNOSTIC_ONLY.csv", ...
        "Q2_Published_vs_Diagnostic_Reproduced.csv", "FinalPaperObjective"); ...
    profile_definition("Q3", "Q3_Runs_Raw_DIAGNOSTIC_ONLY.csv", ...
        "Q3_Published_vs_Diagnostic_Reproduced.csv", "FinalPaperObjective")];

Profile = strings(numel(definitions), 1);
P1 = zeros(numel(definitions), 1);
P2 = zeros(numel(definitions), 1);
P3 = zeros(numel(definitions), 1);
P4 = zeros(numel(definitions), 1);
RequiredPassPattern = false(numel(definitions), 1);

for index = 1:numel(definitions)
    definition = definitions(index);
    runs = readtable(fullfile(evidence, definition.runFile), ...
        "TextType", "string", "VariableNamingRule", "preserve");
    runIds = numeric_column(runs, "Run");
    if height(runs) ~= 10 || any(~isfinite(runIds) | ...
            runIds < 1 | runIds ~= fix(runIds)) || ...
            numel(unique(runIds)) ~= 10
        error("fastverify:InvalidRetainedRuns", ...
            "%s does not contain ten unique runs.", definition.name);
    end
    firstPerfect = numeric_column(runs, "FirstPerfectGeneration");
    reported = numeric_column(runs, "ReportedIteration");
    objectives = numeric_column(runs, definition.objectiveColumn);
    if any(isinf(firstPerfect)) || any(~isfinite(reported)) || ...
            any(~isfinite(objectives))
        error("fastverify:InvalidRetainedNumericValue", ...
            "%s contains malformed/nonfinite run metrics.", definition.name);
    end
    historicalReproduced = [ ...
        mean(isfinite(firstPerfect) & firstPerfect <= 1000); ...
        mean(isfinite(firstPerfect) & firstPerfect <= 2000); ...
        median(reported); ...
        mean(objectives)];
    gateMetrics = historicalReproduced;
    gateMetrics(4) = max(abs(objectives));

    verification = readtable(fullfile(evidence, definition.verificationFile), ...
        "TextType", "string", "VariableNamingRule", "preserve");
    if height(verification) < 4
        error("fastverify:IncompleteRetainedVerification", ...
            "%s verification has fewer than four required gates.", definition.name);
    end
    retainedReproduced = numeric_column(verification, "Reproduced");
    retainedRequiredNumeric = numeric_column(verification, "Required");
    retainedPassNumeric = numeric_column(verification, "Pass");
    retainedReproduced = retainedReproduced(1:4);
    retainedRequiredNumeric = retainedRequiredNumeric(1:4);
    retainedPassNumeric = retainedPassNumeric(1:4);
    if any(~isfinite(retainedReproduced)) || ...
            any(~ismember(retainedRequiredNumeric, [0, 1])) || ...
            any(~ismember(retainedPassNumeric, [0, 1]))
        error("fastverify:InvalidRetainedVerificationValue", ...
            "%s verification contains malformed gate values.", definition.name);
    end
    retainedRequired = logical(retainedRequiredNumeric);
    retainedPass = logical(retainedPassNumeric);
    tolerance = 1e-12 * max(1, abs(historicalReproduced));
    if any(abs(retainedReproduced - historicalReproduced) > tolerance)
        error("fastverify:RetainedGateArithmeticMismatch", ...
            "%s gate arithmetic does not match its run ledger.", definition.name);
    end
    derivedPattern = logical([ ...
        abs(gateMetrics(1) - 0.9) / 0.9 <= 0.05; ...
        abs(gateMetrics(2) - 1.0) <= 0.05; ...
        abs(gateMetrics(3) - 1000) / 1000 <= 0.05; ...
        all(abs(objectives) <= 1e-12)]);
    expectedPattern = logical([1; 0; 1; 0]);
    if ~all(retainedRequired) || ...
            ~isequal(retainedPass, derivedPattern) || ...
            ~isequal(derivedPattern, expectedPattern)
        error("fastverify:RetainedGatePatternMismatch", ...
            "%s is not the recorded P1/P3-pass, P2/P4-fail result.", ...
            definition.name);
    end

    Profile(index) = definition.name;
    P1(index) = gateMetrics(1);
    P2(index) = gateMetrics(2);
    P3(index) = gateMetrics(3);
    P4(index) = gateMetrics(4);
    RequiredPassPattern(index) = isequal(retainedPass, expectedPattern);
end

failureLog = readtable(fullfile(workspace, "failure_logs", "Failure_Log.csv"), ...
    "TextType", "string", "VariableNamingRule", "preserve");
usa = failureLog(failureLog.candidate_id == "USA-001", :);
if height(usa) ~= 1 || numeric_column(usa, "diagnostic_cycles") ~= 3
    error("fastverify:MissingFinalFailureLog", ...
        "USA-001 final three-cycle failure row is missing.");
end
detailed = string(fileread(fullfile(workspace, ...
    "failure_logs", "USA-001_primary_failure.md")));
requiredStatus = ...
    "Status: primary failed; Q1 failed; Q2 failed; Q3 failed; diagnostic limit exhausted";
if ~contains(detailed, requiredStatus)
    error("fastverify:DetailedFailureStatusMismatch", ...
        "Detailed USA-001 final failure status is missing.");
end
if isfolder(fullfile(workspace, "candidate_02_degroot_adaptive_ga"))
    error("fastverify:DeletedCandidateReturned", ...
        "The failed candidate directory unexpectedly exists.");
end

report = struct();
report.passed = true;
report.evidenceManifestSHA256 = expectedManifestHash;
report.manifestFileCount = height(manifest);
report.profileGates = table(Profile, P1, P2, P3, P4, RequiredPassPattern);
report.candidateDirectoryAbsent = true;
report.elapsedSeconds = toc(started);

if verbose
    fprintf("Retained evidence verification: PASS\n");
    fprintf("Files: %d; profiles: %d; elapsed: %.3f s\n", ...
        report.manifestFileCount, height(report.profileGates), ...
        report.elapsedSeconds);
    disp(report.profileGates);
end
end

function definition = profile_definition(name, runFile, verificationFile, objective)
definition = struct("name", string(name), "runFile", string(runFile), ...
    "verificationFile", string(verificationFile), ...
    "objectiveColumn", string(objective));
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
