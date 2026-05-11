# Project Notes

The project has been reduced to one active path: MATLAB `ga`.

Main flow:

```text
main -> optimoptions('ga') -> ga -> gnn_fitness -> mlp_predict -> c_index_error
```

Removed from the active path:

- custom GA loop;
- custom SAGA loop;
- adaptive GA sandbox;
- method wrapper layer;
- sandbox operator comparison.

The only non-MATLAB-GA code left is problem code: data generation, MLP prediction, and c-index fitness.
