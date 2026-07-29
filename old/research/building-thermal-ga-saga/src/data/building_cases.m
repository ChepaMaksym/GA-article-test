function cases = building_cases(caseFilter)
if nargin < 1
    caseFilter = [];
end

space = building_design_space();
n = numel(space.gene_names);
windows = 2:10;
insulation = 11:13;
glazing = 1;
infiltration = 14;
orientation = 15;

cases = repmat(empty_case(), 1, 7);
cases(1) = make_case(1, 'windows_area', windows, n);
cases(2) = make_case(2, 'windows_area_orientation', [windows, orientation], n);
cases(3) = make_case(3, 'insulation', insulation, n);
cases(4) = make_case(4, 'insulation_orientation', [insulation, orientation], n);
cases(5) = make_case(5, 'glazing_windows_insulation', [glazing, windows, insulation], n);
cases(6) = make_case(6, 'glazing_windows_insulation_orientation', [glazing, windows, insulation, orientation], n);
cases(7) = make_case(7, 'all_variables', [glazing, windows, insulation, infiltration, orientation], n);

if ~isempty(caseFilter)
    keep = false(1, numel(cases));
    for i = 1:numel(cases)
        keep(i) = any(cases(i).id == caseFilter);
    end
    cases = cases(keep);
end
end

function item = empty_case()
item = struct('id', [], 'label', '', 'optimize_mask', [], 'data_class', 'synthetic_reproduction');
end

function item = make_case(id, label, activeGenes, nGenes)
mask = false(1, nGenes);
mask(activeGenes) = true;
item = empty_case();
item.id = id;
item.label = label;
item.optimize_mask = mask;
end
