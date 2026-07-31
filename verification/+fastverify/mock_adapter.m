function checkpoint = mock_adapter(runId, seedLedger, targetGeneration, prior, scenario)
%MOCK_ADAPTER Deterministic adapter used only to test the harness.

scenario = string(scenario);
if ~isempty(prior)
    if string(prior.resumeState.scenario) ~= scenario || ...
            ~isequaln(orderfields(prior.seedLedger), ...
                orderfields(seedLedger)) || ...
            double(prior.runId) ~= double(runId)
        error("fastverify:MockResumeMismatch", ...
            "Mock prior state belongs to another run or scenario.");
    end
end
algorithmSeed = seedLedger.algorithmSeed;

switch scenario
    case "fail_p1"
        if runId <= 8
            firstPerfectThreshold = 500;
        else
            firstPerfectThreshold = NaN;
        end
    case {"fail_p2", "corrupt"}
        if runId <= 9
            firstPerfectThreshold = 500;
        else
            firstPerfectThreshold = NaN;
        end
    case "pass_full"
        if runId <= 9
            firstPerfectThreshold = 500;
        else
            firstPerfectThreshold = 1500;
        end
    otherwise
        error("fastverify:UnknownMockScenario", ...
            "Unknown mock scenario: %s", scenario);
end

if isfinite(firstPerfectThreshold) && ...
        firstPerfectThreshold <= targetGeneration
    firstPerfect = firstPerfectThreshold;
else
    firstPerfect = NaN;
end
perfect = isfinite(firstPerfect);
if perfect
    objective = 0;
    if firstPerfect <= 1000
        reportedIteration = 1000;
    else
        reportedIteration = 2000;
    end
else
    objective = 0.01 + double(runId) / 1000 + 1 / double(targetGeneration);
    reportedIteration = targetGeneration;
end
isTerminal = perfect || targetGeneration >= 100000;
resumeState = struct("generation", targetGeneration, ...
    "scenario", scenario, "seedLedger", seedLedger);
rngState = uint32([double(seedLedger.instanceSeed), ...
    double(seedLedger.populationSeed), double(algorithmSeed), ...
    double(seedLedger.analysisSeed), double(targetGeneration), double(runId)]);

checkpoint = struct( ...
    "runId", double(runId), ...
    "seedLedger", seedLedger, ...
    "reachedGeneration", double(targetGeneration), ...
    "firstPerfectGeneration", firstPerfect, ...
    "reportedIteration", double(reportedIteration), ...
    "perfect", logical(perfect), ...
    "objective", objective, ...
    "evaluationCount", double(targetGeneration) * (100 + double(runId)), ...
    "isTerminal", logical(isTerminal), ...
    "resumeState", resumeState, ...
    "rngState", rngState);
checkpoint.stateHash = fastverify.checkpoint_state_hash(checkpoint);

if scenario == "corrupt"
    checkpoint = rmfield(checkpoint, "rngState");
end
end
