function [agp, agpFitness, egp, egpFitness, agpCount] = article_gene_pool_split(population, fitness, beta)
[fitness, order] = sort(fitness);
population = population(order, :);
populationSize = size(population, 1);
agpCount = max(2, min(populationSize, round(beta * populationSize)));
agp = population(1:agpCount, :);
agpFitness = fitness(1:agpCount);
egp = population(agpCount + 1:end, :);
egpFitness = fitness(agpCount + 1:end);
end
