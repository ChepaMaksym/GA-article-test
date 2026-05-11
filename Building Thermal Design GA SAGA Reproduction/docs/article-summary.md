# Article Summary

The article studies a single-family detached house in Polish temperate climate and optimizes envelope/design choices to reduce life cycle cost. The publisher page reports that MATLAB R2017a was used for the optimization workflow and EnergyPlus was used for building energy simulation.

Design variables encoded in this project:

- glazing type: `G10`, `G07`, `G06`, `G05`;
- nine window areas derived from a 1.5 m height and discrete widths;
- external wall, ground-floor, and attic-ceiling insulation thickness;
- infiltration level;
- building orientation.

Article-backed constants encoded here include the reference building LCC and energy demand, cost/options from the article tables, and the seven optimization-case definitions.

## SGA Classification

The article calls its fuzzy controller a self-adaptive genetic algorithm. The local project plan uses a stricter formal SAGA criterion: `theta_base` must be part of the genotype, changed by variation, and selected with the individual. Because the article controller calculates GA parameters externally from diversity, run stage, and no-improvement count, this repository classifies that article method as `non_saga_external_adaptation`.

The executable optimizer named `formal SAGA` is therefore a redesigned algorithm consistent with the local plan, not a claim that the article's fuzzy SGA satisfies the formal SAGA definition.
