function checkpoint = load_checkpoint(path)
%LOAD_CHECKPOINT Load a checkpoint only after validating its SHA-256.

path = char(string(path));
sidecar = [path, '.sha256'];
if ~isfile(path) || ~isfile(sidecar)
    error("fastverify:IncompleteCheckpoint", ...
        "Checkpoint or SHA-256 sidecar is missing: %s", path);
end

expected = lower(strtrim(string(fileread(sidecar))));
if strlength(expected) ~= 64 || isempty(regexp(expected, "^[0-9a-f]{64}$", "once"))
    error("fastverify:InvalidCheckpointHash", ...
        "Checkpoint sidecar is not a SHA-256 digest: %s", sidecar);
end
actual = fastverify.sha256_file(path);
if actual ~= expected
    error("fastverify:CheckpointHashMismatch", ...
        "Checkpoint SHA-256 mismatch: %s", path);
end

loaded = load(path, "checkpoint");
if ~isfield(loaded, "checkpoint") || ~isstruct(loaded.checkpoint)
    error("fastverify:InvalidCheckpointPayload", ...
        "Checkpoint MAT file has no checkpoint struct: %s", path);
end
checkpoint = loaded.checkpoint;
end
