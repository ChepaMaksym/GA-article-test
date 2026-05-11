function matrix = saga_theta_matrix(population)
matrix = zeros(numel(population), 3);
for i = 1:numel(population)
    matrix(i, :) = theta_to_vector(population(i).theta);
end
end
