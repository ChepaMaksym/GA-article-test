# EU-002 re-audit — hard fail / no-go

Audit date: 2026-07-30  
Candidate: EU-002  
DOI: [10.3390/app12073482](https://doi.org/10.3390/app12073482)  
Decision: **`[audit 2026-07-30] hard_fail`**

## Official identity, affiliation, and legal full text

The audited work is Xin Zhao, Zhili Tang, Fan Cao, Caicheng Zhu, and Jacques Periaux, “An Efficient Hybrid Evolutionary Optimization Method Coupling Cultural Algorithm with Genetic Algorithms and Its Application to Aerodynamic Shape Design,” *Applied Sciences* 12(7), article 3482.

- The [official article](https://www.mdpi.com/2076-3417/12/7/3482) gives **29 March 2022** as the publication date, 23 February 2022 as the received date, and 23 March 2022 as the accepted date.
- Jacques Periaux is affiliated with the International Center for Numerical Methods in Engineering (CIMNE), Universitat Politècnica de Catalunya, 08034 Barcelona, Spain. This is a qualifying EU affiliation. The other four authors are affiliated with Nanjing University of Aeronautics and Astronautics in China.
- The publisher article and PDF are licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
- The [Universitat Politècnica de Catalunya record](https://upcommons.upc.edu/entities/publication/b8895eec-97a4-432d-9ecd-2fa03624d1b2) and its stable [handle](https://hdl.handle.net/2117/430238) contain the article PDF, not a data, code, mesh, or executable archive.

The qualifying identity, publication date, lawful full text, and EU-affiliation filters pass.

## Audited publisher artifact

The bytes audited for the formula, table, and metadata checks were the publisher’s current [`applsci-12-03482-v2.pdf`](https://mdpi-res.com/d_attachment/applsci/applsci-12-03482/article_deploy/applsci-12-03482-v2.pdf):

| Property | Value |
|---|---|
| Bytes | `2,843,091` |
| SHA-256 | `FADC6E9456EF476568F08DE93301242AC885A7B0DF7AD626830B59D7EBA93C6B` |
| MD5 | `35B594CB6EDB82A6FE3490E054C6D588` |
| PDF metadata title | `An Efficient Hybrid Evolutionary Optimization Method Coupling Cultural Algorithm with Genetic Algorithms and Its Application to Aerodynamic Shape Design` |
| PDF metadata creation | `2022-03-30 13:58:07 +08:00` |
| PDF metadata modification | `2022-03-30 08:00:42 +02:00` |

The URL is publisher-controlled rather than content-addressed; the hashes above pin the exact bytes used for this audit. No official source-code commit, release, DOI archive, or immutable data version was found, so no code/data commit or archive hash exists to record.

## Artifact and license boundary

The paper’s Data Availability Statement says that the data are publicly available “in the repository,” but supplies no repository name, URL, DOI, accession number, or bibliographic reference. The official article page and UPC record do not expose a supplemental package.

No official author deposit containing source code, raw benchmark runs, seed ledger, wing geometry, CST vector, CFD mesh, solver configuration, or convergence arrays was identified in searches of the author/publisher records and common code/data archives. Consequently:

- the article text and figures may be reused under CC BY 4.0;
- no code language, code license, commit SHA, dependency manifest, or executable version is available;
- no separate license applies to the absent raw benchmark/CFD artifacts;
- the article license cannot be treated as a license for an unspecified flow solver, mesh, geometry, or unavailable source code.

## Dimensional audit

The dimensional threshold passes in principle, but the engineering vector is not fully bounded.

### Analytic benchmarks

Table 1 lists dimensions 10, 30, and 100 for \(F_1\)–\(F_3\) and \(F_5\)–\(F_7\), and dimensions 12, 32, and 100 for \(F_4\). Several functions therefore exceed the required eleven decision variables. \(F_1\), \(F_2\), \(F_5\), and \(F_6\) have usable high-dimensional expressions.

Three printed definitions require caution:

1. \(F_3\) is printed as
   \[
   F_3=\sum_{i=1}^{n}\sum_{j=1}^{i}x_j
   \]
   without the square used by the conventional cumulative-sum benchmark. On the symmetric box \((-100,100)^D\), the printed linear expression does not have the stated optimum zero.
2. In \(F_7\), the second exponential is printed with \(\cos(2\pi x_i)\) but no summation and an unbound \(i\). The expression is mathematically incomplete.
3. \(F_4\) is printed as
   \[
   \sum_{i=1}^{n}\left[
   (x_{4i-3}+10x_{4i-2})^2+
   5(x_{4i-1}-x_{4i})^2+
   (x_{4i-2}-2x_{4i-1})^4+
   10(x_{4i-3}-x_{4i})^4
   \right].
   \]
   Table 1 calls the dimension \(D\), but does not state the necessary relationship \(n=D/4\). Reading \(n=D\), as elsewhere in the table, indexes beyond the vector.

Repairing these formulas by substituting conventional benchmark definitions would be a clean-room assumption, not exact reproduction of the printed specification.

### Wing vector

Sections 5.1–5.2 state that eight spanwise sections each use nine fourth-order CST parameters, for a claimed \(8\times9=72\)-variable vector:

\[
\left(
R_{le}^{(s)},\beta^{(s)},\beta'^{(s)},
b_1^{(s)},b_2^{(s)},b_3^{(s)},
b_1'^{(s)},b_2'^{(s)},b_3'^{(s)}
\right),\qquad s=1,\ldots,8.
\]

Table 8 supplies only eight bound rows:

| Parameter | Range |
|---|---|
| \(R_{le}/c\) | \((0.004,0.012)\) |
| \(\beta\) rad | \((0.14,0.28)\) |
| \(\beta'\) rad | \((0,0.14)\) |
| \(b_1/c\) | \((0.05,0.20)\) |
| \(b_2/c\) | \((0.10,0.30)\) |
| \(b_3/c\) | \((0.10,0.30)\) |
| \(b_1'/c\) | \((0.05,0.30)\) |
| \(b_2'/c\) | \((0.05,0.30)\) |

The required bound for \(b_3'/c\) is absent. The initial 72-vector, section stations, exact three-dimensional geometry, and baseline thickness values are also absent.

## Reported experiment settings

Table 6 reports the following HCGA settings:

| Setting | Reported value |
|---|---:|
| \(P_c\) | 0.95 |
| \(P_m\) | 0.1 |
| \(T_{\max}\) | 5000 |
| \(\alpha\) | 0.1 |
| \(\beta\) | 0.3 in Table 6; 0.7 in the Equation 16 prose |
| \(\gamma\) | 0.3 |
| \(\mu\) | 0.1 |
| \(K\) | 5 |
| \(p\) | 20% |

For \(F_1\)–\(F_7\), the population is \(2D\); for \(F_8\)–\(F_{10}\), it is \(5D\). Table 7 reports **30 independent runs for every benchmark**. The old registry statement that the run count was not uniform across the benchmark table is incorrect. No seeds, RNG family/version, implementation language, software version, hardware, or dependency environment are reported.

The wing case uses population 150 and 100 evolutionary iterations at Mach 0.785, angle of attack \(1.92^\circ\), and Reynolds number \(2\times10^7\). Its flow model is described only as a compressible full-potential solver with viscous boundary-layer correction on approximately 0.5 million mesh points.

## Adaptive-mechanism conflicts

### Degenerate population “variance”

Equation 10 is printed as

\[
D_T=\frac{1}{N\,l}
\left(
\sum_{i=1}^{N}\sum_{j=1}^{l}x_i^j-\bar{x}^j
\right),
\qquad
\bar{x}^j=\frac1N\sum_{i=1}^{N}x_i^j.
\]

As typeset, \(j\) remains free in the subtracted mean. If the intended interpretation places \(\bar{x}^j\) inside the double sum, the sum of deviations is identically zero for each coordinate. No square or absolute value appears. Substituting a conventional variance would invent a different equation.

### Entropy and Student-t degree of freedom

Equations 12–13 divide the full solution space \(A\) equally into \(L\) “small spaces” and use

\[
S_T=-\sum_{i=1}^{L}p_i\log p_i,\qquad p_i=|A_i|/N.
\]

The paper does not give \(L\), the high-dimensional partition construction, bin boundaries, edge conventions, or empty-bin handling.

Equation 14 is

\[
n=
\left[
1-\ln\left(\frac{D_T+S_T}{D_{\max}+S_{\max}}\right)
\right].
\]

The paper calls the brackets a “least integer function,” but does not define an unambiguous floor/ceiling convention. The old registry’s definite `floor(...)` claim is unsupported. It also does not specify how \(D_{\max}\) and \(S_{\max}\) are obtained, or what happens when diversity is zero and the logarithm receives zero. Although the prose asserts \(n=1\) in the first generation, that value cannot be derived without the missing normalizers.

### Acceptance count

Equation 15 states

\[
n_{\mathrm{Accept}}=\left(p\%+\frac{p\%}{T}\right)N,
\qquad p=20\%.
\]

The prose again mentions an integer function, but the formula contains no rounding brackets and no tie convention. The stepwise algorithm initializes \(T=1\), yet acceptance and belief update occur only when \(T\bmod K=0\). With \(K=5\), the first operative acceptance is therefore at \(T=5\), or 24% of \(N\) before unspecified rounding—not the 40% initial value previously inferred by the registry.

### Influence proportions

Equation 16 defines

\[
P_k(T)=
\begin{cases}
1/N_k,&T=1,\\
\alpha+\beta\,v_k(T-1)/v(T-1),&T\bmod K=0,\\
P_k(T-1),&\text{otherwise}.
\end{cases}
\]

There are \(N_k=3\) knowledge-source types, and the paper explicitly requires

\[
\beta+\alpha N_k=1.
\]

The Equation 16 prose gives \(\alpha=0.1,\beta=0.7\), which satisfies this condition. Table 6 gives \(\alpha=0.1,\beta=0.3\), whose proportions sum to only 0.6. The publication provides no authority for choosing one value. It also gives no rule for \(v(T-1)=0\), probability renormalization, or conversion of proportions into integer counts of affected individuals.

### Historical direction and t-mutation

The maximum historical-memory capacity \(W\) is never assigned. Equation 9 defines direction as the sign of a sum of absolute differences, so the published quantity can only be positive or zero rather than a signed direction.

Equations 17–19 describe situational, normative, and historical Student-t mutations, with \(\gamma=0.3\) and \(\mu=0.1\). They do not state whether a Student-t draw is shared or redrawn by gene, individual, and knowledge source; how out-of-bound values are repaired; how the affected individuals are selected; or how historical memory is filled/replaced.

## GA operator and execution-order audit

The main steps establish this broad order:

1. set parameters;
2. uniformly initialize the population inside the stated bounds, evaluate it, and set \(T=1\);
3. initialize situational, normative, and historical knowledge;
4. evolve/evaluate the GA population and compute \(D_T,S_T,n\);
5. when \(T\bmod K=0\), perform acceptance and update belief-space knowledge;
6. apply the influence functions;
7. stop or increment \(T\) and return to the evolution step.

This is not an executable GA specification. Section 2.1 gives generic GA prose but no selection rule, crossover representation/formula, ordinary mutation distribution, parent/offspring replacement, elitism, minimization-to-fitness mapping, boundary repair, or wing-constraint handling. The belief-space updates are introduced “taking maximization as an example,” while the analytic benchmarks are minimization problems; the required mapping is not stated.

Thus the broad order is visible, but the component operations and edge cases admit materially different implementations.

## Input reconstruction failure

### Analytic branch

A new implementation can evaluate the valid analytic functions, but it cannot recreate the published HCGA trajectory or distribution without choosing corrections and filling in:

- Equation 10’s diversity definition;
- entropy partition \(L\) and its multidimensional bins;
- \(D_{\max},S_{\max}\), integer rounding, zero-diversity behavior, and influence normalization;
- one of the contradictory \(\beta\) values;
- all base GA operators, replacement, repair, and minimization semantics;
- RNG, seeds, software, and t-draw granularity.

### Wing branch

The wing target additionally lacks:

- the ninth CST bound \(b_3'/c\);
- the initial and optimized 72-component vectors;
- section locations, baseline three-dimensional wing geometry, and thickness vector;
- the CFD solver identity, version, license, numerical configuration, and convergence criteria;
- mesh generator/version and the approximately 0.5-million-point mesh;
- boundary-layer coupling/configuration and raw aerodynamic outputs.

“RAE2822 airfoil” and the plotted figures are not sufficient to reconstruct those inputs exactly.

## Quantitative target and the 5% rule

The strongest nonzero, machine-readable high-dimensional benchmark row is Table 7, \(F_4,D=12\), HCGA:

| Quantity | Published value |
|---|---:|
| Population | 24 |
| Maximum iterations | 5000 |
| Independent runs | 30 |
| Best (`Opt`) | \(8.38\times10^{-7}\) |
| Mean | \(2.31\times10^{-6}\) |
| Standard deviation | \(4.89\times10^{-7}\) |

A 5% band around the reported mean is

\[
[2.1945\times10^{-6},\,2.4255\times10^{-6}].
\]

The reported standard deviation implies

\[
\operatorname{SE}
=\frac{4.89\times10^{-7}}{\sqrt{30}}
\approx8.93\times10^{-8}.
\]

The 5% half-width is only \(1.29\) standard errors. Under an illustrative normal approximation and even treating the reported mean as the true population mean, a fresh 30-run mean has only about an 80% probability of landing inside the 5% band. If both the published and reproduction means are regarded as independent 30-run estimates from the same distribution, the difference has standard error

\[
4.89\times10^{-7}\sqrt{2/30}\approx1.26\times10^{-7},
\]

and the approximate agreement probability falls to about 64%. The raw 30 values are absent, so distribution shape and uncertainty cannot be checked. Near-zero rows in Table 7 make relative-error comparisons still more ill-conditioned.

For the wing case, Table 9 reports:

| Quantity | Baseline | Optimized |
|---|---:|---:|
| \(C_L\) | 0.447 | 0.447 |
| \(C_D\) | 0.01605 | 0.01302 |
| \(C_{Dwave}\) | 0.0024 | 0.0003 |
| \(C_{DPD}\) | 0.0068 | 0.00602 |
| \(C_{DIND}\) | 0.00685 | 0.0067 |
| \(Ma\,L/D\) | 21.863 | 26.938 |

These values are machine-readable but cannot be regenerated without the missing geometry, mesh, solver, and configuration. Therefore neither Table 7 nor Table 9 supplies a suitable exact-reproduction target under the required \(\le5\%\) rule.

## Compute and dependency feasibility

For \(F_4,D=12\), the nominal workload is

\[
24\times5000\times30=3.6\text{ million}
\]

individual evaluations, plus initial evaluations. That is inexpensive in MATLAB or Python. Student-t sampling is available through MATLAB’s Statistics and Machine Learning Toolbox or NumPy, but availability of a distribution sampler does not resolve the missing reference RNG and operator semantics.

The complete Table 7 experiment is on the order of hundreds of millions of objective evaluations and remains feasible with vectorization. Entropy cost cannot be assessed exactly because the partition construction is undefined.

The wing workload is \(150\times100=15{,}000\) approximately half-million-point flow solutions. It likely requires substantial HPC time, but runtime cannot be estimated reliably without the missing solver and convergence configuration. More importantly, it cannot be launched lawfully or faithfully from the published artifacts.

## Hard-filter conclusion

**No-go for strict reproduction and for implementation as the next registry candidate.**

The dimensional, publication-date, EU-affiliation, and lawful-full-text filters pass. The decisive reproducibility filter fails:

- the central adaptive diversity equation is degenerate or ill-formed as printed;
- entropy construction and normalization are unspecified;
- \(\beta=0.7\) in prose conflicts with \(\beta=0.3\) in Table 6;
- rounding, zero-denominator, memory-capacity, draw-granularity, repair, and GA-operator semantics are missing;
- the 72-variable wing vector lacks one bound and all executable CFD inputs;
- no code, seed ledger, raw run archive, or uniquely replayable numerical target exists;
- the published stochastic target is not a robust \(\le5\%\) verification gate.

Correcting the formulas or selecting conventional GA operators would create a new paper-inspired implementation, not an exact reproduction. EU-002 therefore has no final reproducibility score, is noneligible for ranking, and must not proceed to candidate implementation.
