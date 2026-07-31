function [contract, identity] = bind_adapter(contract, adapter, options)
%BIND_ADAPTER Freeze verified adapter sources and configuration in contract.

required = ["AdapterFiles", "AdapterConfiguration"];
if ~isstruct(options) || ~all(isfield(options, required))
    error("fastverify:MissingAdapterIdentityOptions", ...
        "Options must contain AdapterFiles and AdapterConfiguration.");
end
identity = fastverify.adapter_identity(adapter, ...
    options.AdapterFiles, options.AdapterConfiguration);
contract.adapterIdentity = identity;
end
