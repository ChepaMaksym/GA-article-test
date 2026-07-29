# Article Summary

The PDF studies genetic neural networks for survival analysis. A small MLP is trained directly on c-index error.

Source-backed model facts used here:

- MLP with two hidden `tanh` nodes and one linear output;
- survival-analysis objective based on c-index error;
- datasets named in the PDF: `PBC(MAYO)`, `LUNG`, `FLCHAIN`, and `NWTCO`.

This project now implements only the MATLAB-native GA flow. Self-adaptive thesis variants are documented by the PDF but are not active code in the minimized project.
