# Analysis: Discovery Cycle 1 (X-Only Negation-Quotient BSGS)
Across 13 test sizes N in [16, 65536] evaluated on 5 frozen quantiles:
1. Baby table entries reduced from m to ceil(m/2) (46.0% - 50.0% reduction).
2. Baby step setup time reduced by 52.5% mean.
3. Total cold execution time achieved 1.41x - 1.56x speedup (mean 1.50x).
4. Sign resolution on x-hits resolved with 100% precision in O(1) integer comparison.
5. Novelty audit confirmed this is known mathematics (negation-map BSGS), successfully validating the automated discovery loop as a positive control.
