function child = mutate_discrete_genome(child, problem, mutationRate, mutationStep)
if nargin < 4
    mutationStep = 1;
end

for j = 1:numel(child)
    if problem.case.optimize_mask(j) && rand < mutationRate
        if rand < 0.70
            delta = randi([-mutationStep, mutationStep]);
            if delta == 0
                delta = 1;
            end
            child(j) = child(j) + delta;
        else
            child(j) = randi([problem.lb(j), problem.ub(j)]);
        end
    end
end
child = apply_case_mask(child, problem);
end
