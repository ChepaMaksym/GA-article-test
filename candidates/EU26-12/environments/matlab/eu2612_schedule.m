function result = eu2612_schedule(initial_population, minimum_population, budget)
% Independently replay population-only accounting through the IOH stop check.
population = initial_population;
used_budget = 0;
logged_evaluations = initial_population;
generations = 0;
while logged_evaluations < budget
    used_budget = used_budget + population;
    logged_evaluations = logged_evaluations + population;
    generations = generations + 1;
    population = eu2612_lpsr(initial_population, minimum_population, budget, used_budget);
    if generations > budget
        error('EU2612:ScheduleTermination', 'Evaluation schedule did not terminate.');
    end
end
result = struct( ...
    'generations', generations, ...
    'used_budget', used_budget, ...
    'logged_evaluations', logged_evaluations, ...
    'terminal_population', population);
end
