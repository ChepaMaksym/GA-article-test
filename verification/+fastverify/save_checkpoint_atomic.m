function save_checkpoint_atomic(path, checkpoint)
%SAVE_CHECKPOINT_ATOMIC Commit a checkpoint plus full-file SHA-256 sidecar.

path = char(string(path));
parent = fileparts(path);
if ~isfolder(parent)
    mkdir(parent);
end

temporaryMat = [tempname(parent), '.mat'];
temporaryHash = [tempname(parent), '.sha256'];
cleanup = onCleanup(@() cleanup_temporary(temporaryMat, temporaryHash));

save(temporaryMat, "checkpoint", "-v7");
hashValue = fastverify.sha256_file(temporaryMat);

fid = fopen(temporaryHash, "wt");
if fid == -1
    error("fastverify:CheckpointHashWriteFailed", ...
        "Cannot create checkpoint hash sidecar.");
end
fprintf(fid, "%s\n", hashValue);
fclose(fid);

[ok, message] = movefile(temporaryMat, path, "f");
if ~ok
    error("fastverify:CheckpointCommitFailed", "%s", message);
end
[ok, message] = movefile(temporaryHash, [path, '.sha256'], "f");
if ~ok
    error("fastverify:CheckpointHashCommitFailed", "%s", message);
end
end

function cleanup_temporary(varargin)
for index = 1:nargin
    if isfile(varargin{index})
        delete(varargin{index});
    end
end
end
