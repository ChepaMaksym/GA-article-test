function decision = evaluate_gate(gate, checkpoints)
%EVALUATE_GATE Evaluate one gate without ever returning an early PASS.

if isempty(checkpoints)
    error("fastverify:NoCheckpoints", "Gate evaluation requires all runs.");
end
checkpoints = checkpoints(:);

switch string(gate.kind)
    case "perfect_fraction"
        firstPerfect = arrayfun(@(x) double(x.firstPerfectGeneration), checkpoints);
        metric = mean(isfinite(firstPerfect) & firstPerfect <= gate.generation);
        absoluteError = abs(metric - double(gate.target));
    case "median_reported_iteration"
        values = arrayfun(@(x) double(x.reportedIteration), checkpoints);
        metric = median(values);
        absoluteError = abs(metric - double(gate.target));
    case "max_absolute_objective"
        values = arrayfun(@(x) double(x.objective), checkpoints);
        metric = max(abs(values - double(gate.target)));
        absoluteError = metric;
    otherwise
        error("fastverify:UnknownGateKind", ...
            "Unsupported gate kind: %s", string(gate.kind));
end

switch string(gate.toleranceMode)
    case "relative"
        if gate.target == 0
            error("fastverify:InvalidRelativeGate", ...
                "Relative tolerance cannot use a zero target.");
        end
        relativeError = absoluteError / abs(double(gate.target));
        passed = relativeError <= double(gate.tolerance);
    case "absolute"
        relativeError = NaN;
        passed = absoluteError <= double(gate.tolerance);
    otherwise
        error("fastverify:UnknownToleranceMode", ...
            "Unsupported tolerance mode: %s", string(gate.toleranceMode));
end

if gate.required && gate.irreversibleAtCheckpoint && ~passed
    status = "FAIL_DECISIVE";
else
    status = "PROCEED";
end

decision = struct( ...
    "gateId", string(gate.id), ...
    "generation", double(gate.generation), ...
    "metric", metric, ...
    "target", double(gate.target), ...
    "absoluteError", absoluteError, ...
    "relativeError", relativeError, ...
    "passed", logical(passed), ...
    "status", status);
end
