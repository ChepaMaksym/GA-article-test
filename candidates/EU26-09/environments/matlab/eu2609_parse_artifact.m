function summary = eu2609_parse_artifact(checkout)
% Independently parse and aggregate the authenticated non-vendored raw file.
if ~(ischar(checkout) || (isstring(checkout) && isscalar(checkout)))
    error('EU2609:Protocol', 'checkout must be a character path');
end
lambda_character = native2unicode(uint8([206 187]), 'UTF-8');
relative = ['Raw/results_20-09-28_06:58:03_OneMax_n100_' ...
    'JA.OnePlusLambdaCommaLambdaSAReset_' lambda_character '100.txt'];
path = fullfile(char(checkout), relative);
file_id = fopen(path, 'rb');
if file_id < 0
    error('EU2609:Protocol', 'cannot open authenticated raw member');
end
cleanup = onCleanup(@() fclose(file_id)); %#ok<NASGU>
payload = fread(file_id, Inf, '*uint8')';
if numel(payload) ~= 48918
    error('EU2609:Container', 'raw byte count differs');
end
if sum(payload == 10) ~= 522 || any(payload == 13) || any(payload == 0)
    error('EU2609:Container', 'raw line endings or control bytes differ');
end
if payload(end) == 10
    error('EU2609:Container', 'raw file unexpectedly ends with LF');
end
text = native2unicode(payload, 'UTF-8');
lines = regexp(text, '\n', 'split');
if numel(lines) ~= 523
    error('EU2609:Protocol', 'raw logical line count differs');
end

metadata = {
    'Experiment configurations'
    'Seed: 885480221'
    'Problem: OneMax'
    sprintf('Size: 100\tk: 1\tExtra: None')
    'Runs: 500'
    'Stop criteria: solved'
    'Max generations (if aplicable): 1000'
    'Max evaluations (if aplicable): 10000'
    'Algorithm: JA.OnePlusLambdaCommaLambdaSAReset'
    'Initial mutation probability: 0.01'
    'Initial offspring population size: 100'
    'Initial crossover probability(if aplicable): 1.0'
    'Mutation updatefactor (if aplicable): 2'
    'Offspring population size update factor (if aplicable): 1.5'
    'Success ratio (if aplicable): 1'
};
for index = 1:numel(metadata)
    if ~strcmp(lines{index}, metadata{index})
        error('EU2609:Protocol', 'raw metadata differs at line %d', index);
    end
end
separator = '------------------------------------------------------------------';
if ~isempty(lines{16}) || ~strcmp(lines{17}, separator)
    error('EU2609:Protocol', 'opening separator differs');
end

escaped_lambda = regexptranslate('escape', lambda_character);
integer = '(?:0|[1-9][0-9]*)';
decimal = '(?:0|[1-9][0-9]*)\.[0-9]+';
pattern = ['^Final results: Run: (' integer ') +Gens: (' integer ...
    ') +Evals: (' integer ') +' escaped_lambda ': (' integer ...
    ') p: (' decimal ') Solved: (True|False)$'];
generations = zeros(1, 500);
evaluations = zeros(1, 500);
final_lambdas = zeros(1, 500);
for run_id = 1:500
    tokens = regexp(lines{17 + run_id}, pattern, 'tokens', 'once');
    if isempty(tokens)
        error('EU2609:Protocol', 'run line %d violates grammar', 17 + run_id);
    end
    observed_run = str2double(tokens{1});
    generation = str2double(tokens{2});
    evaluation = str2double(tokens{3});
    final_lambda = str2double(tokens{4});
    probability = str2double(tokens{5});
    solved = tokens{6};
    if observed_run ~= run_id || ~strcmp(sprintf('%d', observed_run), tokens{1})
        error('EU2609:Protocol', 'run ID differs at row %d', run_id);
    end
    if generation < 1 || generation > 1000 || generation ~= floor(generation)
        error('EU2609:Protocol', 'generation count is invalid');
    end
    if evaluation < 2 || evaluation > 10000 || mod(evaluation, 2) ~= 0 ...
            || evaluation < 2 * generation
        error('EU2609:Protocol', 'evaluation count is invalid');
    end
    if final_lambda < 1 || final_lambda > 100 || final_lambda ~= floor(final_lambda)
        error('EU2609:Protocol', 'final lambda is invalid');
    end
    if ~isfinite(probability) || probability <= 0 || probability > 1 ...
            || eu2609_round_ties_even(probability * 100) ~= final_lambda
        error('EU2609:Protocol', 'mutation probability is invalid');
    end
    if ~strcmp(solved, 'True')
        error('EU2609:Protocol', 'a run is not solved');
    end
    generations(run_id) = generation;
    evaluations(run_id) = evaluation;
    final_lambdas(run_id) = final_lambda;
end
if ~isempty(lines{518}) || ~strcmp(lines{519}, separator)
    error('EU2609:Protocol', 'closing separator differs');
end

generation_total = sum(generations);
evaluation_total = sum(evaluations);
fitness_total = 100 * 500;
lambda_total = sum(final_lambdas);
generation_mean = sprintf('%.3f', generation_total / 500);
evaluation_mean = sprintf('%.3f', evaluation_total / 500);
fitness_mean = sprintf('%.1f', fitness_total / 500);
lambda_mean = sprintf('%.3f', lambda_total / 500);
footers = {
    ['Average generations to solve:' generation_mean]
    ['Average evaluations to solve:' evaluation_mean]
    ['Average fitness:' fitness_mean]
    ['Average lambda:' lambda_mean]
};
for index = 1:numel(footers)
    if ~strcmp(lines{519 + index}, footers{index})
        error('EU2609:Protocol', 'footer %d differs from exact aggregate', index);
    end
end
if generation_total ~= 98168 || evaluation_total ~= 447632 ...
        || fitness_total ~= 50000 || lambda_total ~= 4946
    error('EU2609:Endpoint', 'integer totals differ from frozen endpoint');
end

summary = struct();
summary.run_count = 500;
summary.generation_total = generation_total;
summary.evaluation_total = evaluation_total;
summary.fitness_total = fitness_total;
summary.final_lambda_total = lambda_total;
summary.generation_mean = generation_mean;
summary.evaluation_mean = evaluation_mean;
summary.fitness_mean = fitness_mean;
summary.final_lambda_mean = lambda_mean;
summary.all_solved = true;
end
