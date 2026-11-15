# Claims Ledger: Discovery Cycle 2
## SUPPORTED
- The order-3 endomorphism phi(x,y) = (beta*x, y) on secp256k1 CANNOT be quotiented in 1D bounded interval DLP for N << 2^126 because the scalar action lambda*k (mod n) displaces scalars by >= 2^126, yielding strictly zero intersection with 1D bounded giant steps.
- Established the Interval Boundary Obstruction: group automorphism quotienting requires domain invariance under the group action.

## NOT SUPPORTED
- Does not claim endomorphism speedup is impossible for FULL-GROUP DLP (N ~ n = 2^256), where 2D GLV decomposition is known to yield sqrt(2) or sqrt(6) speedups.

## FALSIFIED
- Falsified hypothesis H-DISC-02: that secp256k1's order-6 automorphism group can yield a 6-fold reduction in bounded interval DLP.

## NEXT TEST
- Discovery Cycle 3: Bounded Pollard Lambda / Kangaroo control branch vs. Interval-Preserving Representation Candidates.
