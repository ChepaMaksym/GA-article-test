function childTheta = saga_crossover_theta(thetaA, thetaB, mask)
valuesA = theta_to_vector(thetaA);
valuesB = theta_to_vector(thetaB);
childValues = valuesA;
childValues(mask) = valuesB(mask);
childTheta = vector_to_theta(childValues);
end
