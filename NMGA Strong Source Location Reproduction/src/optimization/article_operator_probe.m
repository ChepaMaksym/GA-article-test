function probe = article_operator_probe()
population = reshape(1:20, 5, 4);
fitness = [5; 1; 4; 2; 3];
beta = 0.6;
[agp, ~, egp, ~, agpCount] = article_gene_pool_split(population, fitness, beta);

agpParent = [10, 20, 30, 40];
egpParent = [20, 10, 50, 0];
egpInheritanceRate = 0.3;
egpChild = article_egp_crossover(agpParent, egpParent, egpInheritanceRate);

earlyDelta = article_nonuniform_delta(10, 1, 100, 2, 0.5);
lateDelta = article_nonuniform_delta(10, 90, 100, 2, 0.5);

probe = struct();
probe.agp = agp;
probe.egp = egp;
probe.agp_count = agpCount;
probe.egp_count = size(egp, 1);
probe.egp_child = egpChild;
probe.expected_egp_child = [13, 17, 36, 28];
probe.early_delta = earlyDelta;
probe.late_delta = lateDelta;
end
