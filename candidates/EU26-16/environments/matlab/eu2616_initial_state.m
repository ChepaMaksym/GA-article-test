function state = eu2616_initial_state
% Source initial scalar state for Alg.doControl().
state = struct();
state.crossover_probability = 0.5;
state.mutation_probability = 0.5;
state.best_average_fitness = single(0.0);
state.best_fitness = single(-1.0);
state.last_best_generation = 0;
end
