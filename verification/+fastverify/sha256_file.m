function value = sha256_file(path)
%SHA256_FILE Return a lowercase SHA-256 digest of a local file.

path = char(string(path));
fid = fopen(path, "rb");
if fid == -1
    error("fastverify:UnreadableFile", "Cannot open file: %s", path);
end
cleanup = onCleanup(@() fclose(fid));
bytes = fread(fid, Inf, "*uint8");
digest = java.security.MessageDigest.getInstance("SHA-256");
digest.update(typecast(bytes(:), "int8"));
raw = typecast(int8(digest.digest()), "uint8");
value = lower(string(reshape(dec2hex(raw, 2).', 1, [])));
end
