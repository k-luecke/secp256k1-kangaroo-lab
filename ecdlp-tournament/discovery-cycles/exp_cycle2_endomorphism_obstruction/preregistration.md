# Preregistration: Discovery Cycle 2 (Endomorphism Quotient Hypothesis on Bounded DLP)
Hypothesis ID: H-DISC-02
Laboratory: Lab B (Bounded secp256k1)
Target Question: Can the efficiently computable secp256k1 automorphism orbit Aut(E) = <iota, phi> ~= Z_6 be quotiented while preserving cheap bounded-DLP recovery?
Falsifier: If the scalar-side endomorphism action lambda * k (mod n) breaks interval locality such that endomorphism baby steps phi(j * G) have strictly zero collision with bounded 1D giant steps for N << 2^128, or if quotienting requires expanding the search domain to 2D GLV lattice of area >= 2^128 >> N, the hypothesis is FALSIFIED for bounded DLP.
