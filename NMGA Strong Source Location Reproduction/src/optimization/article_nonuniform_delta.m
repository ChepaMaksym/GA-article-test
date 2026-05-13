function delta = article_nonuniform_delta(distanceToBound, generation, maxGenerations, exponent, r)
progress = min(max(generation ./ max(maxGenerations, 1), 0), 1);
delta = distanceToBound .* (1 - r .^ ((1 - progress) .^ exponent));
end
