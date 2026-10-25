"""Theoretical BER over AWGN for the Gray-coded grid formats.

Because each format is two independent PAM axes, the BER is the bit-weighted
average of the per-axis PAM BERs. For an axis with spacing 2d and noise
standard deviation sigma, let x = d / sigma. Then (exact, Gray coding):

    2-PAM:  BER = Q(x)
    4-PAM:  BER = [3 Q(x) + 2 Q(3x) - Q(5x)] / 4

and x follows from the average symbol energy of the format:

    QPSK    Es = 2 d^2   ->  x = sqrt(SNR)
    8-QAM   Es = 6 d^2   ->  x = sqrt(SNR / 3)
    16-QAM  Es = 10 d^2  ->  x = sqrt(SNR / 5)

(with SNR = Es/N0 and sigma^2 = N0/2 per axis). These are exact, not
high-SNR approximations, so the Monte Carlo should agree with them at every
SNR, not just at high SNR.
"""

from __future__ import annotations

import numpy as np
from scipy.special import erfc

from .modulation import Format
from .osnr import db_to_linear, osnr_to_snr_db, DEFAULT_BAUD, DEFAULT_POLS


def qfunc(x: float | np.ndarray) -> float | np.ndarray:
    """Gaussian tail probability Q(x) = P(N(0,1) > x)."""
    return 0.5 * erfc(np.asarray(x) / np.sqrt(2))


def _pam2(x):
    return qfunc(x)


def _pam4(x):
    return (3 * qfunc(x) + 2 * qfunc(3 * x) - qfunc(5 * x)) / 4


def ber_from_snr(fmt: Format, snr_db: float | np.ndarray) -> float | np.ndarray:
    """Exact Gray-coded BER for a format at a given SNR per symbol (dB)."""
    snr = db_to_linear(snr_db)
    fmt = Format(fmt)
    if fmt is Format.QPSK:
        return _pam2(np.sqrt(snr))
    if fmt is Format.QAM8:
        x = np.sqrt(snr / 3)
        return (2 * _pam4(x) + 1 * _pam2(x)) / 3  # 2 bits on I, 1 bit on Q
    if fmt is Format.QAM16:
        return _pam4(np.sqrt(snr / 5))
    raise ValueError(f"unsupported format: {fmt}")


def ber_from_osnr(
    fmt: Format,
    osnr_db: float | np.ndarray,
    baud: float = DEFAULT_BAUD,
    pols: int = DEFAULT_POLS,
) -> float | np.ndarray:
    """Theoretical BER for a format at a given OSNR (dB, 0.1 nm reference)."""
    return ber_from_snr(fmt, osnr_to_snr_db(osnr_db, baud, pols))
