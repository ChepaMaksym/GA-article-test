function lcc = life_cycle_cost(heatingKwhM2, coolingKwhM2, incrementalInvestmentCost, problem)
space = problem.design_space;
reported = problem.reported;

if problem.no_cooling
    ref = reported.reference.no_cooling;
else
    ref = reported.reference.cooling;
end

floorArea = space.reference.floor_area_m2;
etaH = 0.78;
etaC = 3.79;
priceGas = 0.0394;
priceElectricity = 0.1294;

annualCost = annual_energy_cost(heatingKwhM2, coolingKwhM2, floorArea, etaH, etaC, priceGas, priceElectricity);
refAnnualCost = annual_energy_cost(ref.heating_kwh_m2, ref.cooling_kwh_m2, floorArea, etaH, etaC, priceGas, priceElectricity);
discountFactor = ref.lcc_eur / refAnnualCost;

lcc = incrementalInvestmentCost + discountFactor * annualCost;
end

function cost = annual_energy_cost(heatingKwhM2, coolingKwhM2, floorArea, etaH, etaC, priceGas, priceElectricity)
heatingKwh = heatingKwhM2 * floorArea;
coolingKwh = coolingKwhM2 * floorArea;
cost = (heatingKwh / etaH) * priceGas + (coolingKwh / etaC) * priceElectricity;
end
