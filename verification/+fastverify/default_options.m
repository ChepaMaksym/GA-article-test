function options = default_options()
%DEFAULT_OPTIONS PC-aware defaults for staged GA verification.

options = struct();
options.UseParallel = true;
options.WorkerCount = 4;
options.PoolType = "Processes";
options.AllowSequentialFallback = true;
options.ReuseCache = true;
options.CacheDirectory = fullfile(tempdir, "ga_fast_verification");
options.AdapterFiles = strings(0, 1);
options.AdapterConfiguration = struct();
end
