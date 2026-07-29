function cases = synthetic_fault_cases(kind)
if nargin < 1 || isempty(kind)
    kind = 'reproduction';
end

baseSections = [4, 9, 15, 18, 22, 25, 29, 32];
cases = repmat(empty_case(), 1, numel(baseSections));
for i = 1:numel(baseSections)
    cases(i) = make_case(sprintf('case_%02d_section_%02d', i, baseSections(i)), baseSections(i), 0, 'full', 1.0);
end

if strcmpi(kind, 'unit')
    cases = make_case('unit_section_09', 9, 0, 'full', 1.0);
elseif strcmpi(kind, 'sandbox')
    extra = [ ...
        make_case('noisy_single_flip', 12, 1, 'full', 1.4), ...
        make_case('noisy_double_flip', 24, 2, 'full', 1.8), ...
        make_case('missing_every_third_ftu', 27, 0, 'missing_every_third', 1.6), ...
        make_case('sparse_terminal_ftu', 32, 0, 'sparse_terminal', 2.0), ...
        make_case('difficult_section_32_noisy', 32, 1, 'full', 2.2)];
    cases = [cases, extra]; %#ok<AGROW>
elseif ~strcmpi(kind, 'reproduction')
    error('Unknown synthetic fault case kind: %s', kind);
end
end

function c = make_case(name, faultSection, flipCount, sensorMode, weight)
c = empty_case();
c.data_type = 'synthetic_reproduction';
c.name = name;
c.true_fault_section = faultSection;
c.flip_count = flipCount;
c.sensor_mode = sensorMode;
c.weight = weight;
c.note = 'Synthetic FTU observation; not original article upload data.';
end

function c = empty_case()
c = struct( ...
    'data_type', '', ...
    'name', '', ...
    'true_fault_section', NaN, ...
    'flip_count', NaN, ...
    'sensor_mode', '', ...
    'weight', NaN, ...
    'note', '');
end
