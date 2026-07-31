function tests = test_fast_verification
tests = functiontests(localfunctions);
end

function testFailDecisivelyAtP1(testCase)
[options, cleanup] = make_test_options(false); %#ok<ASGLU>
adapter = @(runId, seed, target, prior) ...
    fastverify.mock_adapter(runId, seed, target, prior, "fail_p1");
report = run_bound(adapter, fastverify.usa001_contract(), options);

verifyEqual(testCase, report.status, "FAIL_DECISIVE");
verifyEqual(testCase, report.stoppedAtGeneration, 1000);
verifyFalse(testCase, report.fullVerificationCompleted);
verifyEqual(testCase, numel(report.stageLog), 1);
verifyEqual(testCase, report.stageLog(1).executedRuns, 10);
verifyEqual(testCase, report.decisions(1).status, "FAIL_DECISIVE");
verifyNotEqual(testCase, report.decisions(1).status, "PASS");
end

function testFailDecisivelyAtP2AndSkipTerminal(testCase)
[options, cleanup] = make_test_options(false); %#ok<ASGLU>
adapter = @(runId, seed, target, prior) ...
    fastverify.mock_adapter(runId, seed, target, prior, "fail_p2");
report = run_bound(adapter, fastverify.usa001_contract(), options);

verifyEqual(testCase, report.status, "FAIL_DECISIVE");
verifyEqual(testCase, report.stoppedAtGeneration, 2000);
verifyFalse(testCase, report.fullVerificationCompleted);
verifyEqual(testCase, report.terminalGateStatus, ...
    "NOT_EVALUATED_AFTER_DECISIVE_QUALIFICATION_FAILURE");
verifyEqual(testCase, [report.stageLog.executedRuns], [10, 1]);
verifyEqual(testCase, report.decisions(1).status, "PROCEED");
verifyEqual(testCase, report.decisions(2).status, "FAIL_DECISIVE");
verifyFalse(testCase, any(string({report.decisions.status}) == "PASS"));
end

function testFullPassOnlyAfterQualification(testCase)
[options, cleanup] = make_test_options(false); %#ok<ASGLU>
adapter = @(runId, seed, target, prior) ...
    fastverify.mock_adapter(runId, seed, target, prior, "pass_full");
report = run_bound(adapter, fastverify.usa001_contract(), options);

verifyEqual(testCase, report.status, "PASS_FULL");
verifyTrue(testCase, report.fullVerificationCompleted);
verifyEqual(testCase, report.stoppedAtGeneration, 100000);
verifyEqual(testCase, [report.stageLog.generation], [1000, 2000, 100000]);
verifyEqual(testCase, [report.stageLog.executedRuns], [10, 1, 0]);
verifyTrue(testCase, all([report.finalDecisions.passed]));
verifyFalse(testCase, any(string({report.decisions.status}) == "PASS"));
end

function testP4RejectsSingleObjectiveOutlier(testCase)
[options, cleanup] = make_test_options(false); %#ok<ASGLU>
options.AdapterConfiguration = struct("scenario", "p4_outlier");
adapter = @p4_outlier_adapter;
contract = fastverify.usa001_contract();
contract.perfectObjectiveTolerance = 1e-11;
report = run_bound(adapter, contract, options);

verifyEqual(testCase, report.status, "FAIL_FULL");
p4 = report.finalDecisions(string({report.finalDecisions.gateId}) == "P4");
verifyEqual(testCase, p4.metric, 5e-12, "AbsTol", 0);
verifyFalse(testCase, p4.passed);
verifyGreaterThan(testCase, p4.metric, contract.gates(4).tolerance);
end

function testIncompleteAdapterResultFailsClosed(testCase)
[options, cleanup] = make_test_options(false); %#ok<ASGLU>
adapter = @(runId, seed, target, prior) ...
    fastverify.mock_adapter(runId, seed, target, prior, "corrupt");
verifyError(testCase, @() run_bound( ...
    adapter, fastverify.usa001_contract(), options), ...
    "fastverify:IncompleteAdapterResult");
end

function testIntegrityCheckedCacheReuseAndCorruptionRejection(testCase)
[options, cleanup] = make_test_options(false); %#ok<ASGLU>
adapter = @(runId, seed, target, prior) ...
    fastverify.mock_adapter(runId, seed, target, prior, "fail_p2");
first = run_bound(adapter, fastverify.usa001_contract(), options);
second = run_bound(adapter, fastverify.usa001_contract(), options);
verifyEqual(testCase, [second.stageLog.cacheHits], [10, 1]);
verifyEqual(testCase, [second.stageLog.executedRuns], [0, 0]);

path = fullfile(char(first.cacheDirectory), "run_001_g000001000.mat");
junk = 1;
save(path, "junk");
verifyError(testCase, @() run_bound( ...
    adapter, fastverify.usa001_contract(), options), ...
    "fastverify:CheckpointHashMismatch");
end

function testAdapterIdentityPreventsCrossAdapterCacheReuse(testCase)
[options, cleanup] = make_test_options(false); %#ok<ASGLU>
scenarioA = "fail_p1";
adapterA = @(runId, seed, target, prior) ...
    fastverify.mock_adapter(runId, seed, target, prior, scenarioA);
options.AdapterConfiguration = struct("scenario", scenarioA);
contractA = fastverify.bind_adapter( ...
    fastverify.usa001_contract(), adapterA, options);
first = fastverify.run_staged(adapterA, contractA, options);

scenarioB = "fail_p2";
adapterB = @(runId, seed, target, prior) ...
    fastverify.mock_adapter(runId, seed, target, prior, scenarioB);
options.AdapterConfiguration = struct("scenario", scenarioB);
contractB = fastverify.bind_adapter( ...
    fastverify.usa001_contract(), adapterB, options);
second = fastverify.run_staged(adapterB, contractB, options);

verifyNotEqual(testCase, first.adapterIdentity.sha256, ...
    second.adapterIdentity.sha256);
verifyNotEqual(testCase, first.cacheDirectory, second.cacheDirectory);
verifyEqual(testCase, [second.stageLog.cacheHits], [0, 0]);
verifyEqual(testCase, [second.stageLog.executedRuns], [10, 1]);
verifyEqual(testCase, second.status, "FAIL_DECISIVE");
end

function testBoundAdapterIdentityPayloadCannotBeMutated(testCase)
[options, cleanup] = make_test_options(false); %#ok<ASGLU>
adapter = @(runId, seed, target, prior) ...
    fastverify.mock_adapter(runId, seed, target, prior, "fail_p1");
contract = fastverify.bind_adapter( ...
    fastverify.usa001_contract(), adapter, options);
contract.adapterIdentity.configuration.suite = "tampered_after_binding";

verifyError(testCase, @() fastverify.run_staged( ...
    adapter, contract, options), ...
    "fastverify:AdapterIdentityMismatch");
end

function testNonzeroObjectiveTargetUsesOneDeviation(testCase)
gate = fastverify.usa001_contract().gates(4);
gate.target = 1;
gate.tolerance = 0.2;
checkpoints = [struct("objective", 0.8); struct("objective", 1.1)];

decision = fastverify.evaluate_gate(gate, checkpoints);

verifyEqual(testCase, decision.metric, 0.2, "AbsTol", 10 * eps);
verifyEqual(testCase, decision.absoluteError, 0.2, ...
    "AbsTol", 10 * eps);
verifyTrue(testCase, decision.passed);
end

function testPreterminalNonirreversibleGateUsesScheduledState(testCase)
[options, cleanup] = make_test_options(false); %#ok<ASGLU>
options.AdapterConfiguration = struct( ...
    "suite", "fastverify_tests", "scenario", "staged_objective");
contract = fastverify.usa001_contract();
for gateIndex = 1:2
    contract.gates(gateIndex).required = false;
    contract.gates(gateIndex).irreversibleAtCheckpoint = false;
end
contract.gates(3).target = 100000;
contract.gates(3).tolerance = 0;
contract.gates(4).target = 2;
contract.gates(4).tolerance = 0;
contract.gates(4).required = false;
earlyGate = contract.gates(4);
earlyGate.id = "EARLY_OBJECTIVE";
earlyGate.generation = 1500;
earlyGate.target = 1;
earlyGate.required = true;
contract.gates(end + 1) = earlyGate;

report = run_bound(@staged_objective_adapter, contract, options);
earlyDecision = report.finalDecisions( ...
    string({report.finalDecisions.gateId}) == "EARLY_OBJECTIVE");

verifyEqual(testCase, report.status, "PASS_FULL");
verifyEqual(testCase, [report.stageLog.generation], ...
    [1000, 1500, 2000, 100000]);
verifyEqual(testCase, earlyDecision.metric, 0, "AbsTol", 0);
verifyTrue(testCase, earlyDecision.passed);
verifyEqual(testCase, [report.checkpoints.objective], ...
    2 * ones(1, report.runCount), "AbsTol", 0);
end

function testFutureFirstPerfectGenerationIsRejected(testCase)
[options, cleanup] = make_test_options(false); %#ok<ASGLU>
adapter = @future_first_perfect_adapter;
verifyError(testCase, @() run_bound( ...
    adapter, fastverify.usa001_contract(), options), ...
    "fastverify:InvalidFirstPerfectGeneration");
end

function testGateSchemaAndIrreversibilityFailClosed(testCase)
[options, cleanup] = make_test_options(false); %#ok<ASGLU>
adapter = @(runId, seed, target, prior) ...
    fastverify.mock_adapter(runId, seed, target, prior, "fail_p1");

numericFlag = fastverify.usa001_contract();
numericFlag.gates(1).required = 1;
verifyError(testCase, @() run_bound(adapter, numericFlag, options), ...
    "fastverify:InvalidGateFlag");

noRequired = fastverify.usa001_contract();
for index = 1:numel(noRequired.gates)
    noRequired.gates(index).required = false;
    noRequired.gates(index).irreversibleAtCheckpoint = false;
end
verifyError(testCase, @() run_bound(adapter, noRequired, options), ...
    "fastverify:NoRequiredGates");

noTerminalRequired = fastverify.usa001_contract();
terminal = [noTerminalRequired.gates.generation] == ...
    noTerminalRequired.maximumGeneration;
for index = find(terminal)
    noTerminalRequired.gates(index).required = false;
end
verifyError(testCase, @() run_bound( ...
    adapter, noTerminalRequired, options), ...
    "fastverify:MissingRequiredTerminalGate");

unsafe = fastverify.usa001_contract();
unsafe.gates(1).kind = "max_absolute_objective";
verifyError(testCase, @() run_bound(adapter, unsafe, options), ...
    "fastverify:UnsafeIrreversibleGate");

negativeTolerance = fastverify.usa001_contract();
negativeTolerance.gates(1).tolerance = -0.01;
verifyError(testCase, @() run_bound( ...
    adapter, negativeTolerance, options), ...
    "fastverify:InvalidGateNumericValue");

characterTolerance = fastverify.usa001_contract();
characterTolerance.gates(1).tolerance = '0';
verifyError(testCase, @() run_bound( ...
    adapter, characterTolerance, options), ...
    "fastverify:InvalidGateNumericValue");
end

function testStateHashCoversScientificCheckpoint(testCase)
[options, cleanup] = make_test_options(false); %#ok<ASGLU>
adapter = @(runId, seed, target, prior) ...
    fastverify.mock_adapter(runId, seed, target, prior, "fail_p1");
report = run_bound(adapter, fastverify.usa001_contract(), options);
path = fullfile(char(report.cacheDirectory), "run_001_g000001000.mat");
loaded = load(path, "checkpoint");
checkpoint = loaded.checkpoint;
checkpoint.evaluationCount = checkpoint.evaluationCount + 1;
save(path, "checkpoint", "-v7");
write_hash_sidecar(path);

verifyError(testCase, @() run_bound( ...
    adapter, fastverify.usa001_contract(), options), ...
    "fastverify:CheckpointStateHashMismatch");
end

function testNonfiniteCountersAreRejected(testCase)
[evaluationOptions, evaluationCleanup] = make_test_options(false); %#ok<ASGLU>
verifyError(testCase, @() run_bound( ...
    @infinite_evaluations_adapter, fastverify.usa001_contract(), ...
    evaluationOptions), "fastverify:InvalidEvaluationCount");

[reportedOptions, reportedCleanup] = make_test_options(false); %#ok<ASGLU>
verifyError(testCase, @() run_bound( ...
    @infinite_reported_adapter, fastverify.usa001_contract(), ...
    reportedOptions), "fastverify:InvalidReportedIteration");
end

function testSequentialAndParallelOutcomesMatch(testCase)
[serialOptions, serialCleanup] = make_test_options(false); %#ok<ASGLU>
[parallelOptions, parallelCleanup] = make_test_options(true); %#ok<ASGLU>
parallelOptions.WorkerCount = 2;
adapter = @(runId, seed, target, prior) ...
    fastverify.mock_adapter(runId, seed, target, prior, "fail_p2");
serial = run_bound(adapter, fastverify.usa001_contract(), serialOptions);
parallel = run_bound(adapter, fastverify.usa001_contract(), parallelOptions);

verifyEqual(testCase, parallel.status, serial.status);
verifyEqual(testCase, [parallel.decisions.metric], [serial.decisions.metric], ...
    "AbsTol", 0);
verifyEqual(testCase, string({parallel.checkpoints.stateHash}), ...
    string({serial.checkpoints.stateHash}));
end

function testRetainedEvidenceVerifier(testCase)
report = verify_retained_evidence();
verifyTrue(testCase, report.passed);
verifyEqual(testCase, report.manifestFileCount, 25);
verifyTrue(testCase, all(report.profileGates.RequiredPassPattern));
end

function testHistoricalRuntimeProjection(testCase)
analysis = analyze_historical_runtime();
verifyGreaterThan(testCase, analysis.historicalMinutes, 140);
verifyLessThan(testCase, analysis.failFastSerialMinutes, 16);
verifyGreaterThan(testCase, ...
    analysis.theoreticalBarrierLowerBoundMinutes, 4);
verifyLessThan(testCase, ...
    analysis.theoreticalBarrierLowerBoundMinutes, 5);
verifyGreaterThan(testCase, analysis.projectedLPTFourWorkerMinutes, 5);
verifyLessThan(testCase, analysis.projectedLPTFourWorkerMinutes, 6);
verifyLessThan(testCase, ...
    analysis.theoreticalBarrierLowerBoundMinutes, ...
    analysis.projectedLPTFourWorkerMinutes);
verifyLessThan(testCase, analysis.empiricalFourWorkerComputeMinutes, 7);
verifyGreaterThan(testCase, analysis.empiricalFourWorkerComputeMinutes, 5);
end

function testInvalidProvenanceIsRejected(testCase)
[options, cleanup] = make_test_options(false); %#ok<ASGLU>
contract = fastverify.usa001_contract();
contract.provenance.implementationSHA256 = "not-a-hash";
adapter = @(runId, seedLedger, target, prior) ...
    fastverify.mock_adapter(runId, seedLedger, target, prior, "fail_p1");
verifyError(testCase, @() run_bound(adapter, contract, options), ...
    "fastverify:InvalidProvenanceHash");
end

function testWrongSeedLedgerIsRejected(testCase)
[options, cleanup] = make_test_options(false); %#ok<ASGLU>
adapter = @wrong_seed_adapter;
verifyError(testCase, @() run_bound( ...
    adapter, fastverify.usa001_contract(), options), ...
    "fastverify:CheckpointIdentityMismatch");
end

function testMockResumeMatchesUninterruptedState(testCase)
contract = fastverify.usa001_contract();
seedLedger = contract.seedLedger(10);
direct = fastverify.mock_adapter(10, seedLedger, 100000, [], "fail_p2");
first = fastverify.mock_adapter(10, seedLedger, 1000, [], "fail_p2");
resumed = fastverify.mock_adapter(10, seedLedger, 100000, first, "fail_p2");
verifyEqual(testCase, resumed.objective, direct.objective, "AbsTol", 0);
verifyEqual(testCase, resumed.evaluationCount, direct.evaluationCount);
verifyEqual(testCase, resumed.rngState, direct.rngState);
verifyEqual(testCase, resumed.stateHash, direct.stateHash);
end

function [options, cleanup] = make_test_options(useParallel)
directory = tempname;
mkdir(directory);
cleanup = onCleanup(@() remove_test_directory(directory));
options = fastverify.default_options();
options.UseParallel = useParallel;
options.WorkerCount = 2;
options.CacheDirectory = directory;
options.AdapterFiles = [string(which("fastverify.mock_adapter")); ...
    string(mfilename("fullpath")) + ".m"];
options.AdapterConfiguration = struct("suite", "fastverify_tests");
end

function report = run_bound(adapter, contract, options)
contract = fastverify.bind_adapter(contract, adapter, options);
report = fastverify.run_staged(adapter, contract, options);
end

function remove_test_directory(directory)
if isfolder(directory)
    rmdir(directory, "s");
end
end

function checkpoint = wrong_seed_adapter(runId, seedLedger, target, prior)
checkpoint = fastverify.mock_adapter( ...
    runId, seedLedger, target, prior, "fail_p1");
checkpoint.seedLedger.algorithmSeed = ...
    checkpoint.seedLedger.algorithmSeed + uint32(1);
end

function checkpoint = future_first_perfect_adapter( ...
        runId, seedLedger, target, prior)
checkpoint = fastverify.mock_adapter( ...
    runId, seedLedger, target, prior, "fail_p2");
checkpoint.firstPerfectGeneration = double(target) + 1;
checkpoint.perfect = false;
end

function checkpoint = infinite_evaluations_adapter( ...
        runId, seedLedger, target, prior)
checkpoint = fastverify.mock_adapter( ...
    runId, seedLedger, target, prior, "fail_p1");
checkpoint.evaluationCount = Inf;
end

function checkpoint = infinite_reported_adapter( ...
        runId, seedLedger, target, prior)
checkpoint = fastverify.mock_adapter( ...
    runId, seedLedger, target, prior, "fail_p1");
checkpoint.reportedIteration = Inf;
end

function checkpoint = p4_outlier_adapter( ...
        runId, seedLedger, target, prior)
checkpoint = fastverify.mock_adapter( ...
    runId, seedLedger, target, prior, "pass_full");
if runId == 10 && target >= 2000
    checkpoint.objective = 5e-12;
    checkpoint.stateHash = fastverify.checkpoint_state_hash(checkpoint);
end
end

function checkpoint = staged_objective_adapter( ...
        runId, seedLedger, target, prior)
checkpoint = fastverify.mock_adapter( ...
    runId, seedLedger, target, prior, "fail_p1");
checkpoint.firstPerfectGeneration = NaN;
checkpoint.perfect = false;
if target < 100000
    checkpoint.objective = 1;
else
    checkpoint.objective = 2;
end
checkpoint.reportedIteration = double(target);
checkpoint.isTerminal = target >= 100000;
checkpoint.stateHash = fastverify.checkpoint_state_hash(checkpoint);
end

function write_hash_sidecar(path)
fid = fopen(char(string(path) + ".sha256"), "wt");
if fid == -1
    error("fastverify:TestSidecarWriteFailed", ...
        "Could not rewrite the test checkpoint sidecar.");
end
cleanup = onCleanup(@() fclose(fid));
fprintf(fid, "%s\n", fastverify.sha256_file(path));
end
