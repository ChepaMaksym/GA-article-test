# Article Summary

## Source
- Article: **Genetic algorithm optimization of negative pressure wave method for robust real time leak detection in long distance pipelines**
- Journal: Scientific Reports, volume 15, article 36429, 2025
- URL: https://www.nature.com/articles/s41598-025-20525-5

## Research Goal
The article proposes a hybrid **GA-NPW** method for long-distance pipeline leak localization. The goal is to improve conventional negative pressure wave localization by dynamically tuning the parameters that strongly affect the NPW equation:

- wave speed `a`;
- fluid velocity `v`;
- leak position `x`;
- sensor time alignment.

## Reported Experimental Context
- Pipeline: 175 km crude-oil transmission pipeline.
- Diameter: 22 inch.
- Validation: 10 controlled field leak tests.
- Sampling rate: 200 Hz.
- Methods compared: conventional NPW, HGI, and GA-NPW.

## Article GA Configuration
The paper reports the selected GA configuration as:

- population size: `80`;
- iterations: `200`;
- crossover rate: `0.3`;
- mutation rate: `0.05`;
- selection: tournament selection.

The reported reason for this configuration is a balance between localization accuracy, convergence behavior, and computation time.

In this reproduction, the controlled synthetic validation uses known leak positions as validation targets. This is separated from deployment use because real-time unknown leaks would not provide the target position during detection.

## Reported Metrics
The paper evaluates:

- localization error percent;
- localization deviation in meters or kilometers;
- MAE;
- RMSE;
- standard deviation of localization error;
- detection delay;
- computation time per detection cycle.

## Reported Reference Results
The paper reports these high-level reference results:

- conventional NPW average localization error: approximately `11%`;
- HGI average localization error: approximately `18%`;
- GA-NPW average localization error: approximately `5%`;
- detection delay: approximately `10 s` for GA-NPW versus `30-40 s` for traditional methods;
- GA-NPW computation time: under approximately `350 ms` per detection cycle in the reported configuration.

## Robustness Checks Reported By The Paper
The article discusses robustness under:

- wave-speed deviation of about `+/-10%`;
- high operational noise;
- flow-rate variation from `60%` to `120%` of nominal;
- sensor synchronization error up to `2 s`;
- pipeline length scaling from `50 km` to `300 km`.
