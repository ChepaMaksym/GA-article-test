function report = run_staged(adapter, contract, options)
%RUN_STAGED Run immutable GA seeds through fail-closed published milestones.
%
% The qualification stages can return only FAIL_DECISIVE or PROCEED.
% PASS_FULL is possible only after the terminal/full-verification stage.

if nargin < 3 || isempty(options)
    options = fastverify.default_options();
end
validate_inputs(adapter, contract, options);
actualAdapterIdentity = fastverify.adapter_identity(adapter, ...
    options.AdapterFiles, options.AdapterConfiguration);
if ~isequaln(orderfields(actualAdapterIdentity), ...
        orderfields(contract.adapterIdentity))
    error("fastverify:AdapterIdentityMismatch", ...
        "Current adapter sources/configuration do not match the contract.");
end

contractSignature = fastverify.checkpoint_state_hash( ...
    struct("contract", contract));
cacheRoot = fullfile(char(options.CacheDirectory), ...
    sprintf("%s_%s", char(contract.id), extractBefore(contractSignature, 17)));
if ~isfolder(cacheRoot)
    mkdir(cacheRoot);
end

stageGenerations = unique([[contract.gates.generation], ...
    contract.maximumGeneration]);

runCount = numel(contract.runIds);
states = cell(runCount, 1);
stageLog = repmat(empty_stage_log(), 0, 1);
allDecisions = repmat(empty_decision(), 0, 1);
poolInfo = struct("parallelUsed", false, "workers", 1, "poolClass", "none");

for stageIndex = 1:numel(stageGenerations)
    targetGeneration = stageGenerations(stageIndex);
    active = find(cellfun(@(x) isempty(x) || ~logical(x.isTerminal), states));
    activeBefore = numel(active);
    cacheHits = 0;
    toRun = zeros(0, 1);
    priors = cell(0, 1);

    for item = 1:numel(active)
        stateIndex = active(item);
        runId = contract.runIds(stateIndex);
        cachePath = checkpoint_path(cacheRoot, runId, targetGeneration);
        prior = states{stateIndex};
        if options.ReuseCache && isfile(cachePath)
            cached = fastverify.load_checkpoint(cachePath);
            validate_checkpoint(cached, contract, contractSignature, ...
                actualAdapterIdentity.sha256, stateIndex, ...
                targetGeneration, prior);
            states{stateIndex} = cached;
            cacheHits = cacheHits + 1;
        else
            toRun(end + 1, 1) = stateIndex; %#ok<AGROW>
            priors{end + 1, 1} = prior; %#ok<AGROW>
        end
    end

    generated = cell(numel(toRun), 1);
    if ~isempty(toRun)
        stageRunIds = contract.runIds(toRun);
        stageSeedLedger = contract.seedLedger(toRun);
        [useParallel, workers, poolClass] = choose_execution( ...
            options, numel(toRun));
        poolInfo.parallelUsed = poolInfo.parallelUsed || useParallel;
        poolInfo.workers = max(poolInfo.workers, workers);
        if useParallel
            poolInfo.poolClass = poolClass;
            adapterConstant = parallel.pool.Constant({adapter});
            adapterCleanup = onCleanup(@() delete(adapterConstant));
            parfor (item = 1:numel(toRun), workers)
                localAdapter = adapterConstant.Value{1};
                generated{item} = localAdapter( ...
                    stageRunIds(item), stageSeedLedger(item), ...
                    targetGeneration, priors{item});
            end
            clear adapterCleanup adapterConstant
        else
            for item = 1:numel(toRun)
                generated{item} = adapter( ...
                    stageRunIds(item), stageSeedLedger(item), ...
                    targetGeneration, priors{item});
            end
        end

        for item = 1:numel(toRun)
            stateIndex = toRun(item);
            prior = priors{item};
            checkpoint = generated{item};
            checkpoint.contractId = string(contract.id);
            checkpoint.contractSignature = contractSignature;
            checkpoint.adapterIdentitySHA256 = ...
                actualAdapterIdentity.sha256;
            checkpoint.checkpointTarget = targetGeneration;
            if isempty(prior)
                checkpoint.previousStateHash = "";
            else
                checkpoint.previousStateHash = string(prior.stateHash);
            end
            checkpoint.stateHash = ...
                fastverify.checkpoint_state_hash(checkpoint);
            validate_checkpoint(checkpoint, contract, contractSignature, ...
                actualAdapterIdentity.sha256, stateIndex, ...
                targetGeneration, prior);
            cachePath = checkpoint_path(cacheRoot, ...
                contract.runIds(stateIndex), targetGeneration);
            fastverify.save_checkpoint_atomic(cachePath, checkpoint);
            states{stateIndex} = checkpoint;
        end
    else
        useParallel = false;
        workers = 1;
    end

    require_stage_coverage(states, targetGeneration);
    stageDecisions = decisions_at_generation( ...
        contract.gates, targetGeneration, states);
    allDecisions = [allDecisions; stageDecisions(:)]; %#ok<AGROW>

    logRow = empty_stage_log();
    logRow.generation = targetGeneration;
    logRow.activeBefore = activeBefore;
    logRow.executedRuns = numel(toRun);
    logRow.cacheHits = cacheHits;
    logRow.parallelUsed = useParallel;
    logRow.workers = workers;
    logRow.decisions = stageDecisions;
    stageLog(end + 1, 1) = logRow; %#ok<AGROW>

    decisive = stageDecisions( ...
        arrayfun(@(x) x.status == "FAIL_DECISIVE", stageDecisions));
    if ~isempty(decisive)
        report = base_report(contract, contractSignature, cacheRoot, ...
            states, stageLog, allDecisions, poolInfo);
        report.status = "FAIL_DECISIVE";
        report.stoppedAtGeneration = targetGeneration;
        report.fullVerificationCompleted = false;
        report.terminalGateStatus = ...
            "NOT_EVALUATED_AFTER_DECISIVE_QUALIFICATION_FAILURE";
        report.decisiveGateIds = string({decisive.gateId}).';
        return
    end
end

finalDecisions = decisions_in_contract_order(contract.gates, allDecisions);
required = [contract.gates.required];
allRequiredPass = all([finalDecisions(required).passed]);

report = base_report(contract, contractSignature, cacheRoot, ...
    states, stageLog, allDecisions, poolInfo);
report.stoppedAtGeneration = contract.maximumGeneration;
report.fullVerificationCompleted = true;
report.terminalGateStatus = "EVALUATED";
report.finalDecisions = finalDecisions;
report.decisiveGateIds = strings(0, 1);
if allRequiredPass
    report.status = "PASS_FULL";
else
    report.status = "FAIL_FULL";
end
end

function validate_inputs(adapter, contract, options)
if ~isa(adapter, "function_handle")
    error("fastverify:InvalidAdapter", "adapter must be a function handle.");
end
if ~isstruct(contract) || ~isscalar(contract)
    error("fastverify:InvalidContract", "Contract must be one scalar struct.");
end
requiredContract = ["id", "runIds", "seedLedger", "maximumGeneration", ...
    "minimumObjective", "perfectObjectiveTolerance", "gates", ...
    "adapterIdentity", "provenance"];
if ~all(isfield(contract, requiredContract))
    error("fastverify:InvalidContract", "Contract fields are incomplete.");
end
if ~isstruct(contract.adapterIdentity) || ...
        ~isscalar(contract.adapterIdentity)
    error("fastverify:InvalidAdapterIdentity", ...
        "Contract adapterIdentity must be one scalar struct.");
end
if ~isnumeric(contract.runIds) || ~isreal(contract.runIds) || ...
        ~isvector(contract.runIds)
    error("fastverify:InvalidRunIds", ...
        "Run IDs must be a real numeric vector.");
end
runIds = double(contract.runIds(:));
if isempty(runIds) || any(~isfinite(runIds) | ...
        runIds < 1 | runIds ~= fix(runIds)) || ...
        numel(unique(runIds)) ~= numel(runIds)
    error("fastverify:InvalidRunIds", "Run IDs must be unique positive integers.");
end
if ~isstruct(contract.seedLedger) || ...
        numel(contract.seedLedger) ~= numel(runIds)
    error("fastverify:SeedCountMismatch", ...
        "Exactly one frozen seed-ledger row is required per run.");
end
requiredSeeds = ["instanceSeed", "populationSeed", ...
    "algorithmSeed", "analysisSeed"];
if ~all(isfield(contract.seedLedger, requiredSeeds))
    error("fastverify:IncompleteSeedLedger", ...
        "Every run requires instance, population, algorithm, and analysis seeds.");
end
for seedName = requiredSeeds
    for seedIndex = 1:numel(contract.seedLedger)
        seed = contract.seedLedger(seedIndex).(seedName);
        if ~is_real_numeric_scalar(seed)
            error("fastverify:InvalidSeedLedger", ...
                "%s values must be real numeric scalars.", seedName);
        end
        seed = double(seed);
        if ~isfinite(seed) || seed < 0 || seed ~= fix(seed) || ...
                seed > double(intmax("uint32"))
            error("fastverify:InvalidSeedLedger", ...
                "%s values must be uint32-compatible scalar integers.", ...
                seedName);
        end
    end
end
if ~is_real_numeric_scalar(contract.maximumGeneration)
    error("fastverify:InvalidMaximumGeneration", ...
        "maximumGeneration must be a real numeric scalar.");
end
if ~is_real_numeric_scalar(contract.minimumObjective) || ...
        ~is_real_numeric_scalar(contract.perfectObjectiveTolerance)
    error("fastverify:InvalidObjectiveContract", ...
        "Objective bound and perfect tolerance must be real numeric scalars.");
end
maximumGeneration = double(contract.maximumGeneration);
minimumObjective = double(contract.minimumObjective);
perfectTolerance = double(contract.perfectObjectiveTolerance);
if ~isscalar(maximumGeneration) || ~isfinite(maximumGeneration) || ...
        maximumGeneration < 1 || maximumGeneration ~= fix(maximumGeneration)
    error("fastverify:InvalidMaximumGeneration", ...
        "maximumGeneration must be a positive integer.");
end
if ~isscalar(minimumObjective) || ~isfinite(minimumObjective) || ...
        ~isscalar(perfectTolerance) || ~isfinite(perfectTolerance) || ...
        perfectTolerance < 0
    error("fastverify:InvalidObjectiveContract", ...
        "Objective bound and perfect tolerance must be finite.");
end
requiredProvenance = ["sourceRevision", "publishedTargetSHA256", ...
    "instanceSpecSHA256", "implementationSHA256"];
if ~isstruct(contract.provenance) || ~isscalar(contract.provenance) || ...
        ~all(isfield(contract.provenance, requiredProvenance))
    error("fastverify:IncompleteProvenance", ...
        "Contract provenance hashes are incomplete.");
end
sourceRevision = lower(string(contract.provenance.sourceRevision));
if ~is_text_scalar(contract.provenance.sourceRevision) || ...
        strlength(sourceRevision) ~= 40 || ...
        isempty(regexp(sourceRevision, "^[0-9a-f]{40}$", "once"))
    error("fastverify:InvalidSourceRevision", ...
        "Source revision must be a fixed 40-character commit hash.");
end
for name = requiredProvenance(2:end)
    value = lower(string(contract.provenance.(name)));
    if ~is_text_scalar(contract.provenance.(name)) || ...
            strlength(value) ~= 64 || ...
            isempty(regexp(value, "^[0-9a-f]{64}$", "once"))
        error("fastverify:InvalidProvenanceHash", ...
            "%s must be a SHA-256 digest.", name);
    end
end
requiredAdapterIdentity = ["schemaVersion", "functionText", ...
    "sourceManifest", "configuration", "sha256"];
if ~isstruct(contract.adapterIdentity) || ...
        ~isscalar(contract.adapterIdentity) || ...
        ~all(isfield(contract.adapterIdentity, requiredAdapterIdentity))
    error("fastverify:UnboundAdapterIdentity", ...
        "Bind the adapter to the contract before running.");
end
adapterDigest = string(contract.adapterIdentity.sha256);
if ~is_text_scalar(contract.adapterIdentity.sha256) || ...
        ~isscalar(adapterDigest) || strlength(adapterDigest) ~= 64 || ...
        isempty(regexp(adapterDigest, "^[0-9a-f]{64}$", "once"))
    error("fastverify:InvalidAdapterIdentity", ...
        "Contract adapter identity must be a lowercase SHA-256.");
end
requiredGate = ["id", "kind", "generation", "target", "tolerance", ...
    "toleranceMode", "required", "irreversibleAtCheckpoint"];
if ~isstruct(contract.gates) || isempty(contract.gates) || ...
        ~all(isfield(contract.gates, requiredGate))
    error("fastverify:InvalidGates", "Gate fields are incomplete.");
end
supportedKinds = ["perfect_fraction", "median_reported_iteration", ...
    "max_absolute_objective"];
supportedToleranceModes = ["relative", "absolute"];
gateIds = strings(numel(contract.gates), 1);
requiredMask = false(numel(contract.gates), 1);
for gateIndex = 1:numel(contract.gates)
    gate = contract.gates(gateIndex);
    if ~is_text_scalar(gate.id)
        error("fastverify:InvalidGateIds", ...
            "Gate IDs must be text scalars.");
    end
    gateIds(gateIndex) = string(gate.id);
    if ~is_real_numeric_scalar(gate.generation)
        error("fastverify:InvalidGateGeneration", ...
            "Gate generation must be a real numeric scalar.");
    end
    if ~is_real_numeric_scalar(gate.target) || ...
            ~is_real_numeric_scalar(gate.tolerance)
        error("fastverify:InvalidGateNumericValue", ...
            "Gate target/tolerance must be real numeric scalars.");
    end
    generation = double(gate.generation);
    target = double(gate.target);
    tolerance = double(gate.tolerance);
    if ~isscalar(generation) || ~isfinite(generation) || ...
            generation < 1 || generation ~= fix(generation) || ...
            generation > maximumGeneration
        error("fastverify:InvalidGateGeneration", ...
            "Gate generations must be integers inside the full budget.");
    end
    if ~isscalar(target) || ~isfinite(target) || ...
            ~isscalar(tolerance) || ~isfinite(tolerance) || tolerance < 0
        error("fastverify:InvalidGateNumericValue", ...
            "Gate target/tolerance must be finite and tolerance nonnegative.");
    end
    kind = string(gate.kind);
    toleranceMode = string(gate.toleranceMode);
    if ~is_text_scalar(gate.kind) || ...
            ~isscalar(kind) || ~any(kind == supportedKinds)
        error("fastverify:UnknownGateKind", ...
            "Unsupported gate kind: %s", kind);
    end
    if ~is_text_scalar(gate.toleranceMode) || ...
            ~isscalar(toleranceMode) || ...
            ~any(toleranceMode == supportedToleranceModes)
        error("fastverify:UnknownToleranceMode", ...
            "Unsupported tolerance mode: %s", toleranceMode);
    end
    if toleranceMode == "relative" && target == 0
        error("fastverify:InvalidRelativeGate", ...
            "Relative tolerance cannot use a zero target.");
    end
    if kind == "perfect_fraction" && (target < 0 || target > 1)
        error("fastverify:InvalidPerfectFractionGate", ...
            "Perfect-fraction target must be within [0,1].");
    end
    if ~islogical(gate.required) || ~isscalar(gate.required) || ...
            ~islogical(gate.irreversibleAtCheckpoint) || ...
            ~isscalar(gate.irreversibleAtCheckpoint)
        error("fastverify:InvalidGateFlag", ...
            "Gate required/irreversible flags must be logical scalars.");
    end
    requiredMask(gateIndex) = gate.required;
    if gate.irreversibleAtCheckpoint && ...
            (~gate.required || kind ~= "perfect_fraction" || ...
            generation >= maximumGeneration)
        error("fastverify:UnsafeIrreversibleGate", ...
            "Only required preterminal perfect-fraction deadlines are irreversible.");
    end
end
if any(strlength(gateIds) == 0) || numel(unique(gateIds)) ~= numel(gateIds)
    error("fastverify:InvalidGateIds", ...
        "Gate IDs must be nonempty and unique.");
end
if ~any(requiredMask)
    error("fastverify:NoRequiredGates", ...
        "At least one gate must be required.");
end
gateGenerations = [contract.gates.generation].';
if ~any(requiredMask & gateGenerations == maximumGeneration)
    error("fastverify:MissingRequiredTerminalGate", ...
        "At least one required gate must be evaluated at full budget.");
end
requiredOptions = ["UseParallel", "WorkerCount", "PoolType", ...
    "AllowSequentialFallback", "CacheDirectory", "ReuseCache", ...
    "AdapterFiles", "AdapterConfiguration"];
if ~isstruct(options) || ~isscalar(options) || ...
        ~all(isfield(options, requiredOptions))
    error("fastverify:InvalidOptions", "Execution options are incomplete.");
end
logicalOptions = ["UseParallel", "AllowSequentialFallback", "ReuseCache"];
for optionName = logicalOptions
    if ~islogical(options.(optionName)) || ~isscalar(options.(optionName))
        error("fastverify:InvalidLogicalOption", ...
            "%s must be a logical scalar.", optionName);
    end
end
if ~is_real_numeric_scalar(options.WorkerCount)
    error("fastverify:InvalidWorkerCount", ...
        "WorkerCount must be a real numeric scalar.");
end
workers = double(options.WorkerCount);
poolType = string(options.PoolType);
if ~isscalar(workers) || ~isfinite(workers) || ...
        workers < 1 || workers ~= fix(workers)
    error("fastverify:InvalidWorkerCount", ...
        "WorkerCount must be a positive integer.");
end
if ~is_text_scalar(options.PoolType) || ...
        ~isscalar(poolType) || ~any(poolType == ["Processes", "Threads"])
    error("fastverify:InvalidPoolType", ...
        "PoolType must be Processes or Threads.");
end
if ~is_text_scalar(options.CacheDirectory) || ...
        strlength(string(options.CacheDirectory)) == 0
    error("fastverify:InvalidCacheDirectory", ...
        "CacheDirectory cannot be empty.");
end

function result = is_real_numeric_scalar(value)
result = isnumeric(value) && isreal(value) && isscalar(value);
end

function result = is_text_scalar(value)
result = (ischar(value) && isrow(value)) || ...
    (isstring(value) && isscalar(value) && ~ismissing(value));
end
end

function [useParallel, workers, poolClass] = choose_execution(options, taskCount)
useParallel = false;
workers = 1;
poolClass = "none";
if ~options.UseParallel || taskCount < 2
    return
end
requested = max(1, min(double(options.WorkerCount), taskCount));
requestedPoolType = string(options.PoolType);
try
    if ~license("test", "Distrib_Computing_Toolbox")
        error("fastverify:NoParallelLicense", ...
            "Parallel Computing Toolbox is unavailable.");
    end
    pool = gcp("nocreate");
    if isempty(pool)
        pool = parpool(char(requestedPoolType), requested);
    elseif (requestedPoolType == "Processes" && ...
            ~isa(pool, "parallel.ProcessPool")) || ...
            (requestedPoolType == "Threads" && ...
            ~isa(pool, "parallel.ThreadPool"))
        error("fastverify:ExistingPoolTypeMismatch", ...
            "Existing %s does not match requested %s pool.", ...
            class(pool), requestedPoolType);
    end
    workers = min(requested, pool.NumWorkers);
    useParallel = workers > 1;
    poolClass = string(class(pool));
catch exception
    if exception.identifier == "fastverify:ExistingPoolTypeMismatch" || ...
            ~options.AllowSequentialFallback
        rethrow(exception);
    end
    warning("fastverify:SequentialFallback", ...
        "Parallel execution unavailable; using one process: %s", ...
        exception.message);
end
end

function validate_checkpoint(checkpoint, contract, signature, ...
        adapterIdentitySHA256, stateIndex, target, prior)
required = ["runId", "seedLedger", "reachedGeneration", ...
    "firstPerfectGeneration", "reportedIteration", "perfect", ...
    "objective", "evaluationCount", "isTerminal", "resumeState", ...
    "rngState", "stateHash", "contractId", "contractSignature", ...
    "adapterIdentitySHA256", "checkpointTarget", "previousStateHash"];
if ~isstruct(checkpoint) || ~all(isfield(checkpoint, required))
    error("fastverify:IncompleteAdapterResult", ...
        "Adapter checkpoint is missing required fields.");
end
expectedRun = double(contract.runIds(stateIndex));
expectedSeedLedger = contract.seedLedger(stateIndex);
if double(checkpoint.runId) ~= expectedRun || ...
        ~isequaln(orderfields(checkpoint.seedLedger), ...
            orderfields(expectedSeedLedger))
    error("fastverify:CheckpointIdentityMismatch", ...
        "Checkpoint run ID or seed ledger does not match the contract.");
end
if string(checkpoint.contractId) ~= string(contract.id) || ...
        string(checkpoint.contractSignature) ~= signature
    error("fastverify:CheckpointContractMismatch", ...
        "Checkpoint belongs to another contract.");
end
if string(checkpoint.adapterIdentitySHA256) ~= adapterIdentitySHA256
    error("fastverify:CheckpointAdapterMismatch", ...
        "Checkpoint belongs to another adapter identity.");
end
if double(checkpoint.checkpointTarget) ~= target
    error("fastverify:CheckpointTargetMismatch", ...
        "Checkpoint target generation is incorrect.");
end
generation = double(checkpoint.reachedGeneration);
if generation < 0 || generation ~= fix(generation) || generation > target
    error("fastverify:InvalidReachedGeneration", ...
        "Reached generation is outside the requested stage.");
end
if ~logical(checkpoint.isTerminal) && generation ~= target
    error("fastverify:TruncatedCheckpoint", ...
        "A nonterminal checkpoint must reach the requested stage.");
end
objective = double(checkpoint.objective);
if ~isscalar(objective) || ~isfinite(objective) || ...
        objective < double(contract.minimumObjective) - ...
        double(contract.perfectObjectiveTolerance)
    error("fastverify:InvalidObjective", ...
        "Checkpoint objective is nonfinite or below its proven bound.");
end
evaluations = double(checkpoint.evaluationCount);
if ~isscalar(evaluations) || ~isfinite(evaluations) || ...
        evaluations < 0 || evaluations ~= fix(evaluations)
    error("fastverify:InvalidEvaluationCount", ...
        "Evaluation count must be a nonnegative integer.");
end
firstPerfect = double(checkpoint.firstPerfectGeneration);
if ~isscalar(firstPerfect) || ...
        (~isnan(firstPerfect) && (~isfinite(firstPerfect) || ...
        firstPerfect < 0 || firstPerfect ~= fix(firstPerfect) || ...
        firstPerfect > generation))
    error("fastverify:InvalidFirstPerfectGeneration", ...
        "firstPerfectGeneration must be NaN or an observed generation.");
end
derivedPerfect = isfinite(firstPerfect);
if logical(checkpoint.perfect) ~= derivedPerfect
    error("fastverify:PerfectFlagMismatch", ...
        "Perfect flag disagrees with firstPerfectGeneration.");
end
if derivedPerfect && (objective > contract.perfectObjectiveTolerance || ...
        ~logical(checkpoint.isTerminal))
    error("fastverify:InvalidPerfectCheckpoint", ...
        "A perfect run must be terminal with a zero objective.");
end
if ~derivedPerfect && objective <= contract.perfectObjectiveTolerance
    error("fastverify:UnreportedPerfectCheckpoint", ...
        "A zero objective was not recorded as a perfect solution.");
end
reported = double(checkpoint.reportedIteration);
if ~isscalar(reported) || ~isfinite(reported) || ...
        reported < 0 || reported ~= fix(reported)
    error("fastverify:InvalidReportedIteration", ...
        "Reported iteration must be a nonnegative integer.");
end
hashValue = lower(string(checkpoint.stateHash));
if strlength(hashValue) ~= 64 || isempty(regexp(hashValue, ...
        "^[0-9a-f]{64}$", "once"))
    error("fastverify:InvalidStateHash", ...
        "Checkpoint must contain a lowercase SHA-256 state hash.");
end
expectedStateHash = fastverify.checkpoint_state_hash(checkpoint);
if hashValue ~= expectedStateHash
    error("fastverify:CheckpointStateHashMismatch", ...
        "Checkpoint state does not match its harness-derived SHA-256.");
end
if isempty(checkpoint.rngState) || ...
        (~logical(checkpoint.isTerminal) && isempty(checkpoint.resumeState))
    error("fastverify:IncompleteResumeState", ...
        "RNG and resumable state must be preserved.");
end
if isempty(prior)
    expectedPrevious = "";
else
    expectedPrevious = string(prior.stateHash);
    if generation < double(prior.reachedGeneration)
        error("fastverify:GenerationRegression", ...
            "A resumed run cannot move backward.");
    end
    if evaluations < double(prior.evaluationCount)
        error("fastverify:EvaluationCountRegression", ...
            "A resumed run cannot lose completed evaluations.");
    end
    priorFirstPerfect = double(prior.firstPerfectGeneration);
    if isfinite(priorFirstPerfect)
        if firstPerfect ~= priorFirstPerfect
            error("fastverify:FirstPerfectChanged", ...
                "The first observed perfect generation is immutable.");
        end
    elseif isfinite(firstPerfect) && ...
            firstPerfect <= double(prior.reachedGeneration)
        error("fastverify:NoncausalFirstPerfectGeneration", ...
            "A resumed run cannot discover perfection in its saved past.");
    end
end
if string(checkpoint.previousStateHash) ~= expectedPrevious
    error("fastverify:ResumeChainMismatch", ...
        "Checkpoint does not continue the integrity-checked prior state.");
end
end

function require_stage_coverage(states, target)
for index = 1:numel(states)
    state = states{index};
    if isempty(state) || ...
            (~logical(state.isTerminal) && state.reachedGeneration < target)
        error("fastverify:IncompleteStage", ...
            "Run %d did not cover generation %d.", index, target);
    end
end
end

function decisions = decisions_at_generation(gates, generation, states)
selected = find([gates.generation] == generation);
decisions = repmat(empty_decision(), numel(selected), 1);
if isempty(selected)
    return
end
checkpointArray = vertcat(states{:});
for item = 1:numel(selected)
    decisions(item) = fastverify.evaluate_gate( ...
        gates(selected(item)), checkpointArray);
end
end

function decisions = decisions_in_contract_order(gates, stagedDecisions)
decisions = repmat(empty_decision(), numel(gates), 1);
stagedIds = string({stagedDecisions.gateId});
for gateIndex = 1:numel(gates)
    match = find(stagedIds == string(gates(gateIndex).id));
    if numel(match) ~= 1
        error("fastverify:IncompleteGateEvaluation", ...
            "Gate %s was not evaluated exactly once.", ...
            string(gates(gateIndex).id));
    end
    decisions(gateIndex) = stagedDecisions(match);
end
end

function path = checkpoint_path(root, runId, generation)
path = fullfile(root, sprintf("run_%03d_g%09d.mat", runId, generation));
end

function report = base_report(contract, signature, cacheRoot, states, ...
        stageLog, decisions, poolInfo)
report = struct();
report.contractId = string(contract.id);
report.contractSignature = signature;
report.adapterIdentity = contract.adapterIdentity;
report.cacheDirectory = string(cacheRoot);
report.runCount = numel(contract.runIds);
report.runIds = contract.runIds(:);
report.seedLedger = contract.seedLedger(:);
report.checkpoints = vertcat(states{:});
report.stageLog = stageLog;
report.decisions = decisions;
report.parallelUsed = poolInfo.parallelUsed;
report.maximumWorkersUsed = poolInfo.workers;
report.poolClass = poolInfo.poolClass;
end

function value = empty_decision()
value = struct("gateId", "", "generation", NaN, "metric", NaN, ...
    "target", NaN, "absoluteError", NaN, "relativeError", NaN, ...
    "passed", false, "status", "");
end

function value = empty_stage_log()
value = struct("generation", NaN, "activeBefore", 0, ...
    "executedRuns", 0, "cacheHits", 0, "parallelUsed", false, ...
    "workers", 1, "decisions", repmat(empty_decision(), 0, 1));
end
