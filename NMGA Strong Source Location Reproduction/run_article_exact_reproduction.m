function result = run_article_exact_reproduction(profile)
if nargin < 1 || isempty(profile)
    profile = 'article_exact';
end
projectRoot = fileparts(mfilename('fullpath'));
addpath(genpath(fullfile(projectRoot, 'src')));
result = run_article_exact_reproduction_impl(profile);
end
