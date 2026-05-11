function report = verify_project_structure(projectRoot)
if nargin < 1 || isempty(projectRoot)
    projectRoot = find_project_root();
end

required = {
    'README.md'
    'main.m'
    'run_unit_tests.m'
    'run_reproduction.m'
    'run_sandbox.m'
    'src/data/article_metadata.m'
    'src/data/article_reported.m'
    'src/data/building_design_space.m'
    'src/models/building_surrogate_objective.m'
    'src/optimization/run_classical_ga.m'
    'src/optimization/run_saga_optimizer.m'
    'src/optimization/satisfies_saga_criterion.m'
    'src/metrics/compare_ga_saga_runs.m'
    'tests/run_unit_tests_impl.m'
    'sandbox/results'
    };

checks = repmat(struct('path', '', 'passed', false), numel(required), 1);
passCount = 0;
for i = 1:numel(required)
    path = fullfile(projectRoot, required{i});
    checks(i).path = required{i};
    checks(i).passed = exist(path, 'file') == 2 || exist(path, 'dir') == 7;
    if checks(i).passed
        passCount = passCount + 1;
    end
end

report = struct();
report.passed = passCount == numel(required);
report.pass_count = passCount;
report.fail_count = numel(required) - passCount;
report.checks = checks;
end

function projectRoot = find_project_root()
currentDir = fileparts(mfilename('fullpath'));
projectRoot = currentDir;
while exist(fullfile(projectRoot, 'main.m'), 'file') ~= 2
    parentDir = fileparts(projectRoot);
    if strcmp(parentDir, projectRoot)
        error('Project root with main.m was not found.');
    end
    projectRoot = parentDir;
end
end
