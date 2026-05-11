function problem = building_problem(caseDef, noCooling, scenario)
if nargin < 2
    noCooling = false;
end
if nargin < 3 || isempty(scenario)
    scenario = synthetic_sandbox_scenarios();
    scenario = scenario(1);
end

space = building_design_space();
reported = article_reported();

problem = struct();
problem.design_space = space;
problem.reported = reported;
problem.case = caseDef;
problem.no_cooling = logical(noCooling);
problem.scenario = scenario;
problem.fixed_genome = space.reference.genome;
problem.lb = space.bounds.lb;
problem.ub = space.bounds.ub;
problem.nvars = numel(space.gene_names);
problem.data_class = 'synthetic_reproduction';
problem.objective_name = 'deterministic_surrogate_lcc';
end
