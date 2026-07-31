function identity = adapter_identity(adapter, sourceFiles, configuration)
%ADAPTER_IDENTITY Bind adapter behavior to verified source bytes and config.

if ~isa(adapter, "function_handle")
    error("fastverify:InvalidAdapter", "adapter must be a function handle.");
end
files = string(sourceFiles(:));
if isempty(files)
    error("fastverify:MissingAdapterSources", ...
        "AdapterFiles must list the wrapper and implementation sources.");
end
if ~isstruct(configuration) || ~isscalar(configuration)
    error("fastverify:InvalidAdapterConfiguration", ...
        "AdapterConfiguration must be one scalar struct.");
end

manifest = repmat(struct("name", "", "sha256", ""), numel(files), 1);
for index = 1:numel(files)
    path = char(files(index));
    if ~isfile(path)
        error("fastverify:MissingAdapterSource", ...
            "Adapter source file does not exist: %s", path);
    end
    [~, name, extension] = fileparts(path);
    manifest(index).name = string(name) + string(extension);
    manifest(index).sha256 = fastverify.sha256_file(path);
end
[~, order] = sort(string({manifest.name}));
manifest = manifest(order);
if numel(unique(string({manifest.name}))) ~= numel(manifest)
    error("fastverify:DuplicateAdapterSourceName", ...
        "Adapter source file names must be unique within the manifest.");
end

payload = struct( ...
    "schemaVersion", 1, ...
    "functionText", string(func2str(adapter)), ...
    "sourceManifest", manifest, ...
    "configuration", configuration);
identity = payload;
identity.sha256 = fastverify.checkpoint_state_hash(payload);
end
