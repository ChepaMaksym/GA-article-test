function summary = eu2616_parse_yeast(checkout)
% Independently inspect the authenticated Yeast config, ARFF, and label XML.
if ~(ischar(checkout) || (isstring(checkout) && isscalar(checkout)))
    error('EU2616:Input', 'checkout must be a path');
end
checkout = char(checkout);
configPath = fullfile(checkout, 'cfg', 'Yeast.xml');
labelsPath = fullfile(checkout, 'data', 'Yeast', 'Yeast.xml');
trainPath = fullfile(checkout, 'data', 'Yeast', 'Yeast-train1.arff');
testPath = fullfile(checkout, 'data', 'Yeast', 'Yeast-test1.arff');
required = {configPath, labelsPath, trainPath, testPath};
for index = 1:numel(required)
    if ~exist(required{index}, 'file')
        error('EU2616:Evidence', 'required Yeast member is missing');
    end
end

configText = fileread(configPath);
seedTokens = regexp(configText, 'seed="([0-9]+)"', 'tokens');
seeds = zeros(1, numel(seedTokens));
for index = 1:numel(seedTokens)
    seeds(index) = str2double(seedTokens{index}{1});
end
pathTokens = regexp(configText, ...
    '<(?:train-dataset|test-dataset|xml)>([^<]+)</(?:train-dataset|test-dataset|xml)>', ...
    'tokens');
referenced = cell(1, numel(pathTokens));
missing = {};
for index = 1:numel(pathTokens)
    referenced{index} = strtrim(pathTokens{index}{1});
    if ~exist(fullfile(checkout, strrep(referenced{index}, '/', filesep)), 'file')
        missing{end + 1} = referenced{index}; %#ok<AGROW>
    end
end

labelText = fileread(labelsPath);
labelTokens = regexp(labelText, '<label\s+name="([^"]+)"\s*/>', 'tokens');
labels = cell(1, numel(labelTokens));
for index = 1:numel(labelTokens)
    labels{index} = labelTokens{index}{1};
end
if numel(unique(labels)) ~= numel(labels)
    error('EU2616:Evidence', 'label XML names must be unique');
end

train = parse_arff(trainPath);
test = parse_arff(testPath);
if ~strcmp(train.relation, 'Yeast') || ~strcmp(test.relation, 'Yeast')
    error('EU2616:Evidence', 'unexpected ARFF relation');
end
if ~isequal(train.names, test.names) || ~isequal(train.kinds, test.kinds)
    error('EU2616:Evidence', 'train/test attribute declarations differ');
end
isLabel = ismember(train.names, labels);
inputs = train.names(~isLabel);
arffLabels = train.names(isLabel);
if numel(inputs) ~= 103 || numel(labels) ~= 14 || ...
        ~isequal(sort(arffLabels), sort(labels))
    error('EU2616:Evidence', 'Yeast dimensions disagree with XML/contract');
end
if train.rows ~= 1933 || test.rows ~= 484
    error('EU2616:Evidence', 'Yeast fold-1 row counts differ');
end
for index = find(~isLabel)
    if ~strcmpi(strtrim(train.kinds{index}), 'numeric')
        error('EU2616:Evidence', 'Yeast input must be numeric');
    end
end
for index = find(isLabel)
    if ~strcmp(strrep(train.kinds{index}, ' ', ''), '{0,1}')
        error('EU2616:Evidence', 'Yeast label must be binary');
    end
end

summary = struct();
summary.seeds = seeds;
summary.referenced_paths = referenced;
summary.missing_paths = missing;
summary.input_count = numel(inputs);
summary.label_count = numel(labels);
summary.train_rows = train.rows;
summary.test_rows = test.rows;
summary.total_rows = train.rows + test.rows;
summary.paper_replay_ready = false;
end

function result = parse_arff(path)
text = fileread(path);
lines = regexp(text, '\r\n|\n|\r', 'split');
relation = '';
names = {};
kinds = {};
inData = false;
rows = 0;
for lineNumber = 1:numel(lines)
    line = strtrim(lines{lineNumber});
    if isempty(line) || starts_with(line, '%')
        continue;
    end
    if ~inData && ~isempty(regexpi(line, '^@relation\s+', 'once'))
        token = regexp(line, '^@relation\s+(.+)$', 'tokens', 'once', 'ignorecase');
        if isempty(token) || ~isempty(relation)
            error('EU2616:Evidence', 'invalid ARFF relation');
        end
        relation = strip_quotes(strtrim(token{1}));
    elseif ~inData && ~isempty(regexpi(line, '^@attribute\s+', 'once'))
        token = regexp(line, '^@attribute\s+(\S+)\s+(.+)$', 'tokens', 'once', 'ignorecase');
        if isempty(token)
            error('EU2616:Evidence', 'invalid ARFF attribute');
        end
        names{end + 1} = strip_quotes(token{1}); %#ok<AGROW>
        kinds{end + 1} = strtrim(token{2}); %#ok<AGROW>
    elseif ~inData && strcmpi(line, '@data')
        if isempty(relation) || isempty(names)
            error('EU2616:Evidence', 'ARFF data precedes metadata');
        end
        inData = true;
    elseif inData
        if starts_with(line, '{')
            error('EU2616:Evidence', 'sparse ARFF is outside the frozen parser');
        end
        if numel(strsplit(line, ',')) ~= numel(names)
            error('EU2616:Evidence', 'ARFF row width mismatch at line %d', lineNumber);
        end
        rows = rows + 1;
    else
        error('EU2616:Evidence', 'unexpected ARFF directive');
    end
end
if ~inData || rows == 0
    error('EU2616:Evidence', 'incomplete ARFF file');
end
result = struct('relation', relation, 'names', {names}, 'kinds', {kinds}, 'rows', rows);
end

function result = starts_with(value, prefix)
result = strncmp(value, prefix, length(prefix));
end

function value = strip_quotes(value)
if length(value) >= 2 && ((value(1) == '''' && value(end) == '''') || ...
        (value(1) == '"' && value(end) == '"'))
    value = value(2:end - 1);
end
end
