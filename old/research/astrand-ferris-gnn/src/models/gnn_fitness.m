function [fitness, details] = gnn_fitness(weights, problem)
score = mlp_predict(weights, problem.dataset.X, problem.hidden_nodes);
[fitness, details] = c_index_error(score, problem.dataset.time, problem.dataset.event);
details.data_class = problem.data_class;
end
