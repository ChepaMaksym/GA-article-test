function report = verify_project_structure(projectRoot)
if nargin < 1
    projectRoot = fileparts(fileparts(fileparts(mfilename('fullpath'))));
end

required = {
    'README.md'
    'main.m'
    'article/AstrandFerris_BachelorThesis_PostPresentation_.pdf'
    'src/data/article_metadata.m'
    'src/data/article_reported.m'
    'src/data/synthetic_survival_datasets.m'
    'src/models/c_index_error.m'
    'src/models/decode_mlp_weights.m'
    'src/models/gnn_fitness.m'
    'src/models/mlp_predict.m'
    'src/models/mlp_weight_count.m'
    'src/models/train_validation_split.m'
    'tests/run_unit_tests_impl.m'
    'sandbox/results'
    };

checks = repmat(struct('path', '', 'passed', false), numel(required), 1);
passCount = 0;
for i = 1:numel(required)
    path = fullfile(projectRoot, required{i});
    checks(i).path = required{i};
    checks(i).passed = exist(path, 'file') == 2 || exist(path, 'dir') == 7;
    passCount = passCount + double(checks(i).passed);
end

report = struct();
report.passed = passCount == numel(required);
report.pass_count = passCount;
report.fail_count = numel(required) - passCount;
report.checks = checks;
end
