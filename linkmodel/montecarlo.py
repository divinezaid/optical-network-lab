"""Monte Carlo BER over AWGN, used to cross-check the formulas in ber.py.

Send random bits through modulate -> add complex Gaussian noise -> hard
decision, and count bit errors. We keep sending blocks until we have seen
enough errors (so the estimate is statistically meaningful) or hit a bit
budget (so very low BERs don't run forever).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .modulation import Format, constellation, demodulate, modulate
from .osnr import db_to_linear, osnr_to_snr_db, DEFAULT_BAUD, DEFAULT_POLS


@dataclass(frozen=True)
class MonteCarloResult:
    ber: float
    bit_errors: int
    bits: int

    @property
    def std_error(self) -> float:
        """Standard error of the BER estimate (binomial)."""
        return float(np.sqrt(max(self.ber * (1 - self.ber), 1e-300) / self.bits))


def simulate_ber(
    fmt: Format,
    snr_db: float,
    *,
    min_errors: int = 500,
    max_bits: int = 20_000_000,
    block_symbols: int = 100_000,
    seed: int | None = 0,
) -> MonteCarloResult:
    """Estimate BER at a given SNR per symbol (dB) by simulation."""
    rng = np.random.default_rng(seed)
    const = constellation(fmt)
    k = const.bits_per_symbol

    n0 = 1 / db_to_linear(snr_db)  # Es = 1, so N0 = 1/SNR
    sigma = np.sqrt(n0 / 2)  # per real dimension

    errors = bits = 0
    while errors < min_errors and bits < max_bits:
        tx_bits = rng.integers(0, 2, size=block_symbols * k, dtype=np.int8)
        tx = modulate(tx_bits, const)
        noise = sigma * (rng.standard_normal(tx.shape) + 1j * rng.standard_normal(tx.shape))
        rx_bits = demodulate(tx + noise, const)
        errors += int(np.count_nonzero(rx_bits != tx_bits))
        bits += tx_bits.size

    return MonteCarloResult(ber=errors / bits, bit_errors=errors, bits=bits)


def simulate_ber_osnr(
    fmt: Format,
    osnr_db: float,
    baud: float = DEFAULT_BAUD,
    pols: int = DEFAULT_POLS,
    **kwargs,
) -> MonteCarloResult:
    return simulate_ber(fmt, float(osnr_to_snr_db(osnr_db, baud, pols)), **kwargs)
