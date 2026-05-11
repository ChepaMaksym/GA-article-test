function x = repair_discrete_genome(x, lb, ub)
x = round(double(x(:))');
x = max(x, lb);
x = min(x, ub);
end
