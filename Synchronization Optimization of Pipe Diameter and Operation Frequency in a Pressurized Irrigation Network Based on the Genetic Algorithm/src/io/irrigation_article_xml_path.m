function xmlPath = irrigation_article_xml_path(projectRoot)
if nargin == 0 || isempty(projectRoot)
    projectRoot = find_project_root();
end
xmlPath = fullfile(projectRoot, 'article', 'article.xml');
if ~isfile(xmlPath)
    error('Article XML not found: %s', xmlPath);
end
end

function projectRoot = find_project_root()
currentDir = fileparts(mfilename('fullpath'));
projectRoot = currentDir;
while ~isfile(fullfile(projectRoot, 'main.m'))
    parentDir = fileparts(projectRoot);
    if strcmp(parentDir, projectRoot)
        error('Project root with main.m was not found.');
    end
    projectRoot = parentDir;
end
end
