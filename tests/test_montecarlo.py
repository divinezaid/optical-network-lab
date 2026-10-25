"""Model verification: simulated BER must match theory within tolerance.

Tolerance is statistical, not a fixed percentage. With N bits and true BER
p, the error count is binomial, so the estimate has standard deviation
sqrt(p(1-p)/N). We require the simulation to sit within 4 sigma of theory;
a correct model fails that by chance about once in 16,000 runs, and the
seed is fixed so CI results are repeatable.
"""

import numpy as np
import pytest

from linkmodel import Format, ber_from_snr, simulate_ber, simulate_ber_osnr, ber_from_osnr

SIGMA_TOLERANCE = 4.0

# SNR points chosen per format to span BER ~1e-1 down to ~1e-4.
SNR_POINTS_DB = {
    Format.QPSK: [0.0, 4.0, 8.0, 11.0],
    Format.QAM8: [4.0, 8.0, 12.0, 15.0],
    Format.QAM16: [6.0, 10.0, 14.0, 17.0],
}

CASES = [(fmt, snr) for fmt, snrs in SNR_POINTS_DB.items() for snr in snrs]


@pytest.mark.parametrize("fmt,snr_db", CASES, ids=[f"{f.value}@{s}dB" for f, s in CASES])
def test_simulated_ber_matches_theory(fmt, snr_db):
    theory = float(ber_from_snr(fmt, snr_db))
    sim = simulate_ber(fmt, snr_db, min_errors=500, seed=42)

    sigma = np.sqrt(theory * (1 - theory) / sim.bits)
    z = abs(sim.ber - theory) / sigma
    assert sim.bit_errors >= 500, "not enough errors for a meaningful estimate"
    assert z < SIGMA_TOLERANCE, (
        f"{fmt.value} @ {snr_db} dB: sim {sim.ber:.3e} vs theory {theory:.3e} "
        f"({z:.1f} sigma, {sim.bit_errors} errors / {sim.bits} bits)"
    )


def test_osnr_entry_point_matches_theory():
    osnr_db = 14.0
    theory = float(ber_from_osnr(Format.QPSK, osnr_db))
    sim = simulate_ber_osnr(Format.QPSK, osnr_db, min_errors=500, seed=7)
    assert sim.ber == pytest.approx(theory, rel=0.2)


def test_same_seed_is_reproducible():
    a = simulate_ber(Format.QAM16, 12.0, min_errors=200, seed=3)
    b = simulate_ber(Format.QAM16, 12.0, min_errors=200, seed=3)
    assert a == b
