# Replication Report

## Article Resource
- Title: Synchronization Optimization of Pipe Diameter and Operation Frequency in a Pressurized Irrigation Network Based on the Genetic Algorithm
- Authors: Yiyuan Pang, Hong Li, Pan Tang, Chao Chen
- Journal: Agriculture, 2022, Article 673
- DOI: `10.3390/agriculture12050673`
- URL: https://www.mdpi.com/2077-0472/12/5/673

## Replication Scope
This package separates two layers of work:

1. Article-backed checks that encode and verify tables and constants from the bundled XML.
2. An executable GA sandbox that demonstrates the optimization workflow with a simplified surrogate objective.

A full numerical hydraulic reproduction is not claimed because the XML does not bundle the complete Figure 5 network geometry, pipe lengths, hydrant elevations, source MATLAB code, or an EPANET input model.

## Article-Backed Inputs
- Study area: 30 ha
- Annual irrigation quota: 950 mm
- Branch pipes: 10
- Main pipe diameter: 400 mm
- Commercial U-PVC diameters: `[140 160 200 250 315 400]` mm
- Pipe prices: `[28 37 56 90 142 232]` yuan/m

## Encoded Paper Results
- Reported OFM saving: 1.4%
- Reported PDM saving: 10.6%
- Reported SOM saving: 19.3%
- Reported conclusion: synchronized optimization of pipe diameter and operation frequency gives the largest annual-cost reduction.

## Consistency Checks
- `PASS`: DOI is present in XML. 10.3390/agriculture12050673
- `PASS`: MDPI URL is present in metadata. https://www.mdpi.com/2077-0472/12/5/673
- `PASS`: Article title is encoded. Synchronization Optimization of Pipe Diameter and Operation Frequency in a Pressurized Irrigation Network Based on the Genetic Algorithm
- `PASS`: Table 2 dimensions are 10 by 7. [10 7]
- `PASS`: Table 2 branch 1 matches XML. [160 200 250 250 315 315 315]
- `PASS`: Table 3 commercial diameters match XML. [140 160 200 250 315 400]
- `PASS`: Table 3 prices match XML. [28 37 56 90 142 232]
- `PASS`: Table 5 has 15 model-sector rows. 15 rows
- `PASS`: Table 5 SOM sector 5 frequency is 43 Hz. SOM sector 5
- `PASS`: Table 6 PDM branch 1 matches XML. [200 200 200 200 200 200 200]
- `PASS`: Table 6 SOM branch 1 matches XML. [200 200 200 200 250 250 315]
- `PASS`: Table 6 source anomaly is preserved. SOM branch 7 segment 7 = 2
- `PASS`: Reported savings are encoded. SOM 19.3%

## Warnings And Known Limitations
- The XML does not include Appendix MATLAB code or a source-code listing.
- The XML references Figure 5 network layout, but bundled .tif figure files are not present in the project.
- Table 6 contains an apparent source anomaly: SOM branch 7 segment 7 is 2 mm, not a commercial pipe diameter.
- Table 4 pump coefficients are partially represented around an ellipsis in the article table; encoded values preserve the visible XML entries.
- The executable GA sandbox is a surrogate model, not a full EPANET/MATLAB hydraulic reproduction.

## GA Sandbox Result
- Optimizer: `MATLAB ga()`
- Best surrogate objective: `14383.203890`
- Best branch diameters: `[160 200 200 200 160 200 160 160 160 200]` mm
- Best frequencies: `[44 42 43 48 42]` Hz
- Sandbox report: `sandbox/results/ga_sandbox_report.md`

## Reported Designs Re-Evaluated In Sandbox Surrogate
- `PDM`: objective `26621.679241`, network `25325.401374`, energy `1296.277867`, penalty `0.000000`
- `SOM`: objective `21749.815175`, network `20364.018471`, energy `1385.796703`, penalty `0.000000`

## Status
Article-backed data checks passed; full hydraulic reproduction remains blocked by missing layout/source-code inputs.
