function child = article_egp_crossover(agpParent, egpParent, egpInheritanceRate)
child = agpParent + egpInheritanceRate .* (egpParent - agpParent);
end
