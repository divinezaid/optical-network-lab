"""Gray-coded constellations for QPSK, 8-QAM and 16-QAM.

Every format here is a grid built from two PAM axes (I and Q), which keeps
both the mapping and the exact BER formulas simple:

    QPSK   = 2-PAM (I) x 2-PAM (Q)   -> 2 bits/symbol
    8-QAM  = 4-PAM (I) x 2-PAM (Q)   -> 3 bits/symbol  (rectangular 8-QAM)
    16-QAM = 4-PAM (I) x 4-PAM (Q)   -> 4 bits/symbol

Constellations are scaled to an average symbol energy Es = 1, so the noise
variance alone sets the SNR.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np


class Format(str, Enum):
    QPSK = "QPSK"
    QAM8 = "8-QAM"
    QAM16 = "16-QAM"


# Gray-coded PAM: neighbouring amplitude levels differ in exactly one bit.
_PAM_LEVELS = {
    2: (np.array([-1.0, 1.0]), [(0,), (1,)]),
    4: (np.array([-3.0, -1.0, 1.0, 3.0]), [(0, 0), (0, 1), (1, 1), (1, 0)]),
}

# (I-axis PAM order, Q-axis PAM order) for each format.
_AXES = {
    Format.QPSK: (2, 2),
    Format.QAM8: (4, 2),
    Format.QAM16: (4, 4),
}


@dataclass(frozen=True)
class Constellation:
    format: Format
    points: np.ndarray  # complex, shape (M,), average energy 1
    labels: np.ndarray  # int 0/1, shape (M, bits_per_symbol)

    @property
    def order(self) -> int:
        return len(self.points)

    @property
    def bits_per_symbol(self) -> int:
        return self.labels.shape[1]


def constellation(fmt: Format) -> Constellation:
    """Build the unit-energy, Gray-labelled constellation for a format."""
    m_i, m_q = _AXES[Format(fmt)]
    levels_i, gray_i = _PAM_LEVELS[m_i]
    levels_q, gray_q = _PAM_LEVELS[m_q]

    points, labels = [], []
    for li, bi in zip(levels_i, gray_i):
        for lq, bq in zip(levels_q, gray_q):
            points.append(complex(li, lq))
            labels.append(bi + bq)  # I bits first, then Q bits

    pts = np.array(points)
    pts /= np.sqrt(np.mean(np.abs(pts) ** 2))  # normalise to Es = 1
    return Constellation(Format(fmt), pts, np.array(labels, dtype=np.int8))


def modulate(bits: np.ndarray, const: Constellation) -> np.ndarray:
    """Map a flat bit array (length a multiple of k) onto symbols."""
    k = const.bits_per_symbol
    groups = bits.reshape(-1, k)
    # Turn each label row into an integer so we can look up the symbol.
    weights = 1 << np.arange(k - 1, -1, -1)
    label_ids = const.labels @ weights
    lookup = np.empty(const.order, dtype=int)
    lookup[label_ids] = np.arange(const.order)
    return const.points[lookup[groups @ weights]]


def demodulate(symbols: np.ndarray, const: Constellation) -> np.ndarray:
    """Hard-decision, minimum-distance detection back to a flat bit array."""
    distances = np.abs(symbols[:, None] - const.points[None, :])
    nearest = np.argmin(distances, axis=1)
    return const.labels[nearest].reshape(-1)
