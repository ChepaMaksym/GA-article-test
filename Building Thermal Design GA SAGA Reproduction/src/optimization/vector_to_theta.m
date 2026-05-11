function theta = vector_to_theta(values)
theta = struct();
theta.Pm = values(1);
theta.Pc = values(2);
theta.sigma = values(3);
end
