# Claims Ledger: Discovery Cycle 1
## SUPPORTED
- Factoring out the negation automorphism on secp256k1 reduces baby-step precomputation time by 52.5% and table storage by ~50%, yielding a 1.50x cold-start speedup over standard BSGS across N in [16, 65536].
- Exact sign resolution y_i == +/- y_j resolves dual candidate scalars k = L + i*W +/- j in O(1) without spurious collisions.

## NOT SUPPORTED
- Does not represent a novel algorithm (classified as KNOWN; positive control verification of kernel elimination methodology).
- Does not change the O(sqrt(N)) asymptotic exponent (improves constant factor by ~2x in memory and 1.5x in cold wall time).

## OPEN
- Can additional group symmetries (e.g. order-3 endomorphism phi(x,y) = (beta*x, y)) be quotiented in bounded interval DLP?

## FALSIFIED
- Falsified the null hypothesis that sign-elimination overhead or collisions would negate table-reduction benefits.

## NEXT TEST
- Cycle 2: Endomorphism Quotient Hypothesis on Bounded DLP.
