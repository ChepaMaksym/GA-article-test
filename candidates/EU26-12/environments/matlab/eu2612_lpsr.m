function population = eu2612_lpsr(initial_population, minimum_population, budget, used_budget)
% Released linear population-size reduction with explicit ties-to-even.
values = [initial_population, minimum_population, budget, used_budget];
if any(~isfinite(values)) || any(values ~= fix(values))
    error('EU2612:LPSRInteger', 'LPSR inputs must be finite integers.');
end
if minimum_population <= 0 || initial_population < minimum_population
    error('EU2612:LPSRBounds', 'Population bounds are invalid.');
end
if budget <= 0 || used_budget < 0
    error('EU2612:LPSRBudget', 'Budget values are invalid.');
end
raw = (minimum_population - initial_population) / budget * used_budget + initial_population;
population = eu2612_round_ties_even(raw);
population = max(minimum_population, min(initial_population, population));
end
