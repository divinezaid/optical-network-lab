# Stage 1: Optical link model

What it does: given a modulation format and an OSNR, predict the pre-FEC bit
error rate, prove the prediction with an independent simulation, and decide
whether the link should alarm or step down to a more robust format.

## Pieces

### 1. Constellations (`linkmodel/modulation.py`)
- QPSK, 8-QAM and 16-QAM carry 2, 3 and 4 bits per symbol.
- Each one is built as two PAM axes (I and Q). 8-QAM is the rectangular
  4x2 grid.
- **Gray coding**: neighbouring points differ by one bit. Noise usually
  pushes a symbol to its nearest neighbour, so a symbol error then costs
  only one bit error.
- Everything is normalised to average symbol energy Es = 1, so the noise
  level alone sets the SNR.
- `modulate` maps bits to symbols. `demodulate` picks the nearest point
  (hard decision).

### 2. OSNR to SNR (`linkmodel/osnr.py`)
- OSNR is what you measure on an optical spectrum analyser: signal power
  over the noise in a fixed 0.1 nm (12.5 GHz) reference bandwidth.
- The receiver cares about SNR per symbol (Es/N0) in its own bandwidth.
- `SNR = OSNR · 2·B_ref / (p·Rs)`. At 32 GBaud dual-polarisation that
  works out to SNR = OSNR − 4.1 dB.
- Faster symbol rates see more noise, so they need more OSNR for the same
  BER.

### 3. Theoretical BER (`linkmodel/ber.py`)
- Each axis is a PAM signal with independent Gaussian noise, so the BER is
  a weighted average of the per-axis PAM BERs:
  - 2-PAM: Q(x)
  - 4-PAM: [3Q(x) + 2Q(3x) − Q(5x)] / 4
  - x is half the point spacing divided by the noise standard deviation:
    √SNR for QPSK, √(SNR/3) for 8-QAM, √(SNR/5) for 16-QAM.
- These are **exact** for Gray-coded grids. They are not the high-SNR
  approximations, so theory and simulation should agree at every SNR.

### 4. Monte Carlo (`linkmodel/montecarlo.py`)
- Sends random bits through modulate, then adds complex Gaussian noise,
  then demodulates, and counts bit errors.
- It keeps going until it has seen at least N errors. A BER estimate
  depends on the error count, not the bit count.
- The RNG is seeded, so results are reproducible. That matters in a
  regression suite: a flaky test is worse than no test.

### 5. Link behaviour (`linkmodel/link.py`)
- **FEC threshold**: the decoder can correct errors up to a pre-FEC BER of
  3.8e-3 (classic hard-decision FEC, 7% overhead). Above that, the link
  raises `PRE_FEC_BER_EXCEEDS_THRESHOLD`.
- **Required OSNR**: the OSNR at which BER equals the threshold, found with
  a root-finder. At 32 GBaud DP, the results are:

  | Format | Bits/symbol | Required OSNR |
  |--------|-------------|---------------|
  | QPSK   | 2           | 12.6 dB       |
  | 8-QAM  | 3           | 17.2 dB       |
  | 16-QAM | 4           | 19.3 dB       |

- **Margin** is the actual OSNR minus the required OSNR. Operators watch
  this number.
- **Format fallback**: `select_format` picks the highest-capacity format
  that still clears the threshold, with an optional margin. That trades
  capacity for reach.

## Tests (53, about 3 s) and what each proves

| File | What it verifies |
|---|---|
| `test_modulation.py` | Right size and energy for each format, unique labels, Gray property, noiseless round trip |
| `test_ber_theory.py` | Textbook anchor (QPSK 1e-5 at Eb/N0 = 9.6 dB), 16-QAM matches the high-SNR approximation, BER falls with OSNR, BER = 0.5 at zero signal, format ordering, OSNR↔SNR conversion |
| `test_montecarlo.py` | **Model verification**: simulation within 4σ of theory at 12 points (BER 1e-1 down to 1e-4), plus reproducibility |
| `test_link.py` | Required OSNR hits the threshold, alarm below it, no alarm with margin, step-down order, margin respected |

**Why 4σ and not "within 10%"?** With N bits the BER estimate has a
standard deviation of √(p(1−p)/N). A fixed percentage is too loose at high
BER and too tight at low BER. A sigma test scales correctly. A correct
model fails it about once in 16,000 runs, and a fixed seed removes even
that.

**Honest limit:** with 500 errors per point, the test catches real bugs
such as a wrong noise variance (3 dB off) or broken Gray mapping. It does
not catch differences of a few percent, like exact vs approximate 16-QAM
at low SNR (only about 2σ apart). Tighter tolerance costs runtime, and
that trade-off is worth naming.

## Questions you might get

- **Why does higher-order QAM need more OSNR?** Same energy, more points,
  so the points sit closer together and less noise is enough to cross a
  decision boundary.
- **Why is 8-QAM only about 2 dB better than 16-QAM here?** The
  rectangular 8-QAM grid is inefficient. Real transceivers use star or
  circular 8-QAM, which gains about 1 dB. Rectangular was chosen here
  because its exact BER is closed-form. That's a deliberate scope choice.
- **What does AWGN leave out?** Fibre nonlinearity, chromatic dispersion
  and PMD (a real DSP compensates most of these), phase noise, and
  implementation penalties. Real required OSNR is 1–2 dB worse than
  theory.
- **What about soft-decision FEC?** Modern oFEC/SD-FEC tolerates pre-FEC
  BER around 2e-2. The threshold is a parameter, so that's a one-line
  change.
- **How does this relate to SVT/PV work?** It's the same loop: a spec (the
  theory), an independent measurement (Monte Carlo, standing in for a
  test set), a pass/fail criterion with a justified tolerance, and alarm
  behaviour you can verify. Stage 2 exposes this through each node's NBI.
