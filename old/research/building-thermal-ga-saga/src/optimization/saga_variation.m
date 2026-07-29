function [child1, child2, trace] = saga_variation(parent1, parent2, problem, options)
assert(isfield(parent1, 'x') && isfield(parent1, 'theta'), ...
    'SAGA variation requires a complete individual.');
assert(isfield(parent2, 'x') && isfield(parent2, 'theta'), ...
    'SAGA variation requires a complete individual.');

child1 = parent1;
child2 = parent2;
trace = struct();
trace.received_complete_individual = true;
trace.theta_crossover_used = false;

pairPc = min(0.99, max(0, mean([parent1.theta.Pc, parent2.theta.Pc])));
if rand < pairPc
    mask = rand(size(parent1.x)) < 0.5;
    child1.x(mask) = parent2.x(mask);
    child2.x(mask) = parent1.x(mask);

    thetaMask = rand(1, 3) < 0.5;
    child1.theta = saga_crossover_theta(parent1.theta, parent2.theta, thetaMask);
    child2.theta = saga_crossover_theta(parent2.theta, parent1.theta, thetaMask);
    trace.theta_crossover_used = true;
end

beforeTheta1 = theta_to_vector(child1.theta);
beforeTheta2 = theta_to_vector(child2.theta);

child1.theta = mutate_theta(child1.theta, options);
child2.theta = mutate_theta(child2.theta, options);
child1.x = mutate_discrete_genome(child1.x, problem, child1.theta.Pm, max(1, round(child1.theta.sigma)));
child2.x = mutate_discrete_genome(child2.x, problem, child2.theta.Pm, max(1, round(child2.theta.sigma)));
child1.fitness = [];
child2.fitness = [];

afterTheta1 = theta_to_vector(child1.theta);
afterTheta2 = theta_to_vector(child2.theta);
trace.theta_changed = any(abs(afterTheta1 - beforeTheta1) > 1.0e-12) || ...
    any(abs(afterTheta2 - beforeTheta2) > 1.0e-12) || trace.theta_crossover_used;
end

function theta = mutate_theta(theta, options)
values = theta_to_vector(theta);
bounds = [options.ThetaBounds.Pm; options.ThetaBounds.Pc; options.ThetaBounds.sigma];
for i = 1:3
    if rand < options.ThetaMutationRate
        values(i) = values(i) + options.ThetaMutationScale(i) * randn;
    end
    values(i) = max(bounds(i, 1), min(bounds(i, 2), values(i)));
end
theta = vector_to_theta(values);
end
