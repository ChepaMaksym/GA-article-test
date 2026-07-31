function value = sha256_text(textValue)
%SHA256_TEXT Return a lowercase SHA-256 digest of UTF-8 text.

bytes = unicode2native(char(string(textValue)), "UTF-8");
digest = java.security.MessageDigest.getInstance("SHA-256");
digest.update(typecast(uint8(bytes(:)), "int8"));
raw = typecast(int8(digest.digest()), "uint8");
value = lower(string(reshape(dec2hex(raw, 2).', 1, [])));
end
