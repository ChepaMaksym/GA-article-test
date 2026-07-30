projectRoot = fileparts(mfilename('fullpath'));
addpath(genpath(fullfile(projectRoot, 'src')));

result = run_article_exact_reproduction('unit');

fprintf('Article: %s\n', result.article.title);
fprintf('DOI: %s\n', result.article.doi);
fprintf('Profile: %s\n', result.profile);
fprintf('Data provenance: %s\n', result.data_provenance);
fprintf('Protocols: %d\n', numel(result.protocols));
fprintf('Repeats per protocol: %d\n', result.repeat_count);
fprintf('Report: %s\n', result.report_path);
