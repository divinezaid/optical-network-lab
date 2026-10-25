"""OSNR <-> SNR conversion.

OSNR is what an optical spectrum analyser measures: signal power over noise
power in a fixed 0.1 nm reference bandwidth (12.5 GHz at 1550 nm). The
receiver cares about SNR per symbol (Es/N0) in the signal's own bandwidth.
The two are related by the ratio of the bandwidths:

    OSNR = (p * Rs / (2 * B_ref)) * SNR

where Rs is the symbol rate and p is the number of polarisations
(2 for dual-polarisation coherent systems, which carry one stream per
polarisation and split the noise between them).
"""

from __future__ import annotations

import numpy as np

B_REF_HZ = 12.5e9  # 0.1 nm at 1550 nm
DEFAULT_BAUD = 32e9  # 32 GBaud, typical for 100G/200G coherent
DEFAULT_POLS = 2


def db_to_linear(db: float | np.ndarray) -> float | np.ndarray:
    return 10 ** (np.asarray(db) / 10)


def linear_to_db(lin: float | np.ndarray) -> float | np.ndarray:
    return 10 * np.log10(lin)


def osnr_to_snr_db(
    osnr_db: float | np.ndarray,
    baud: float = DEFAULT_BAUD,
    pols: int = DEFAULT_POLS,
) -> float | np.ndarray:
    """SNR per symbol (Es/N0, dB) seen by the receiver for a given OSNR."""
    return np.asarray(osnr_db) + linear_to_db(2 * B_REF_HZ / (pols * baud))


def snr_to_osnr_db(
    snr_db: float | np.ndarray,
    baud: float = DEFAULT_BAUD,
    pols: int = DEFAULT_POLS,
) -> float | np.ndarray:
    return np.asarray(snr_db) - linear_to_db(2 * B_REF_HZ / (pols * baud))
