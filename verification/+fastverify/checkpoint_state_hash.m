function value = checkpoint_state_hash(checkpoint)
%CHECKPOINT_STATE_HASH Hash the complete typed checkpoint state.
%
% The digest covers every adapter and harness field except stateHash itself.
% Values are encoded with class, shape, structure, and raw numeric bytes so
% the hash does not depend on an adapter-supplied summary.

if ~isstruct(checkpoint) || ~isscalar(checkpoint)
    error("fastverify:InvalidCheckpointForHash", ...
        "Checkpoint state hashing requires one scalar struct.");
end
payload = checkpoint;
if isfield(payload, "stateHash")
    payload = rmfield(payload, "stateHash");
end

digest = java.security.MessageDigest.getInstance("SHA-256");
[~, ~, machineEndian] = computer;
isBigEndian = machineEndian == "B";
update_value(payload);
raw = typecast(int8(digest.digest()), "uint8");
value = lower(string(reshape(dec2hex(raw, 2).', 1, [])));

    function update_value(item)
        if isnumeric(item)
            update_text("numeric");
            update_text(class(item));
            update_shape(size(item));
            update_text(string(issparse(item)));
            update_text(string(isreal(item)));
            if issparse(item)
                [rows, columns, entries] = find(item);
                update_value(uint64(rows));
                update_value(uint64(columns));
                update_value(entries);
            else
                update_numeric_bytes(real(item));
                if ~isreal(item)
                    update_numeric_bytes(imag(item));
                end
            end
        elseif islogical(item)
            update_text("logical");
            update_shape(size(item));
            update_bytes(uint8(item(:)));
        elseif ischar(item)
            update_text("char");
            update_shape(size(item));
            update_bytes(unicode2native(char(item(:).'), "UTF-8"));
        elseif isstring(item)
            update_text("string");
            update_shape(size(item));
            for itemIndex = 1:numel(item)
                if ismissing(item(itemIndex))
                    update_text("missing");
                else
                    update_text("present");
                    update_text(item(itemIndex));
                end
            end
        elseif isstruct(item)
            update_text("struct");
            update_shape(size(item));
            names = sort(string(fieldnames(item)));
            update_shape(numel(names));
            for nameIndex = 1:numel(names)
                update_text(names(nameIndex));
                name = char(names(nameIndex));
                for itemIndex = 1:numel(item)
                    update_value(item(itemIndex).(name));
                end
            end
        elseif iscell(item)
            update_text("cell");
            update_shape(size(item));
            for itemIndex = 1:numel(item)
                update_value(item{itemIndex});
            end
        else
            error("fastverify:UnsupportedStateHashType", ...
                "Unsupported checkpoint value type: %s", class(item));
        end
    end

    function update_numeric_bytes(item)
        supported = ["double", "single", "int8", "uint8", "int16", ...
            "uint16", "int32", "uint32", "int64", "uint64"];
        if ~any(class(item) == supported)
            error("fastverify:UnsupportedStateHashType", ...
                "Unsupported numeric checkpoint type: %s", class(item));
        end
        canonical = item(:);
        if isBigEndian
            canonical = swapbytes(canonical);
        end
        update_bytes(typecast(canonical, "uint8"));
    end

    function update_shape(shape)
        dimensions = uint64(shape(:));
        if isBigEndian
            dimensions = swapbytes(dimensions);
        end
        update_bytes(typecast(dimensions, "uint8"));
    end

    function update_text(textValue)
        update_bytes(unicode2native(char(string(textValue)), "UTF-8"));
    end

    function update_bytes(bytes)
        bytes = uint8(bytes(:));
        byteCountValue = uint64(numel(bytes));
        if isBigEndian
            byteCountValue = swapbytes(byteCountValue);
        end
        byteCount = typecast(byteCountValue, "uint8");
        digest.update(typecast(byteCount(:), "int8"));
        if ~isempty(bytes)
            digest.update(typecast(bytes, "int8"));
        end
    end
end
