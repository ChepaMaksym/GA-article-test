function transition = eu2605_crossover_transition( ...
    parent_a, parent_b, preference, cut)
%EU2605_CROSSOVER_TRANSITION Outcome-blind post-selection transition.
% Preference 3 is explicitly the thesis maximum binary extension profile:
% copy the through-parent and complement common loci in both directions. Its
% algebraic result is complement(parent origin); it is not author-code replay.

if nargin < 4
    cut = [];
end
validate_parent(parent_a, 'parent_a');
validate_parent(parent_b, 'parent_b');
if numel(parent_a) ~= numel(parent_b)
    error('EU2605:BadTransitionInput', 'parents must have equal length');
end
if ~isnumeric(preference) || ~isreal(preference) || ~isscalar(preference) ...
        || ~isfinite(preference) || preference ~= fix(preference) ...
        || preference < 0 || preference > 3
    error('EU2605:BadTransitionInput', ...
        'preference must be one of the experimental labels 0..3');
end

if preference == 3
    if ~isempty(cut)
        error('EU2605:BadTransitionInput', ...
            'maximum extension has no one-point cut');
    end
    child_a = maximum_extension_child(parent_a, parent_b);
    child_b = maximum_extension_child(parent_b, parent_a);
    operator = 'thesis_maximum_extension_complement_origin';
else
    if ~isnumeric(cut) || ~isreal(cut) || ~isscalar(cut) ...
            || ~isfinite(cut) || cut ~= fix(cut) ...
            || cut < 1 || cut >= numel(parent_a)
        error('EU2605:BadTransitionInput', ...
            'one-point transitions require an explicit interior integer cut');
    end
    child_a = [parent_a(1:cut), parent_b((cut + 1):end)];
    child_b = [parent_b(1:cut), parent_a((cut + 1):end)];
    operator = 'one_point_explicit_cut';
end

transition = struct( ...
    'operator', operator, ...
    'preference', preference, ...
    'cut', cut, ...
    'children', {{child_a, child_b}});
end

function child = maximum_extension_child(origin, through)
child = through;
common = origin == through;
child(common & through == '0') = '1';
child(common & through == '1') = '0';
expected = origin;
expected(origin == '0') = '1';
expected(origin == '1') = '0';
if ~strcmp(child, expected)
    error('EU2605:InternalInvariant', ...
        'maximum-extension algebra does not complement the origin');
end
end

function validate_parent(bits, name)
if ~ischar(bits) || ~isrow(bits) || numel(bits) < 2 ...
        || any(bits ~= '0' & bits ~= '1')
    error('EU2605:BadTransitionInput', ...
        '%s must be a binary character row of length at least two', name);
end
end
