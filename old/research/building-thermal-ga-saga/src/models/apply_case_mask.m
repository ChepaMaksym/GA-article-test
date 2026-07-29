function x = apply_case_mask(x, problem)
x = repair_discrete_genome(x, problem.lb, problem.ub);
mask = problem.case.optimize_mask;
fixed = problem.fixed_genome;
x(~mask) = fixed(~mask);
x = repair_discrete_genome(x, problem.lb, problem.ub);
end
