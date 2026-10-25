"""Link-level behaviour: FEC threshold check, alarms and format fallback.

A coherent receiver doesn't need zero pre-FEC errors; it needs the pre-FEC
BER below what the FEC decoder can correct. Above that threshold the
post-FEC output starts to fail, so we raise an alarm. Optionally the link
steps down to a more robust (lower-order) format that still clears the
threshold, trading capacity for reach.
"""

from __future__ import annotations

from dataclasses import dataclass

from scipy.optimize import brentq

from .ber import ber_from_osnr
from .modulation import Format
from .osnr import DEFAULT_BAUD, DEFAULT_POLS

# Classic hard-decision FEC (7% overhead, e.g. G.975.1 I.4) threshold.
HD_FEC_THRESHOLD = 3.8e-3

# Highest capacity first: the order we try formats in when stepping down.
FORMATS_BY_CAPACITY = (Format.QAM16, Format.QAM8, Format.QPSK)

ALARM_BER_EXCEEDS_FEC = "PRE_FEC_BER_EXCEEDS_THRESHOLD"


@dataclass(frozen=True)
class LinkStatus:
    format: Format
    osnr_db: float
    ber: float
    fec_threshold: float
    margin_db: float  # OSNR above (or below, if negative) the required OSNR
    alarms: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.alarms


def required_osnr_db(
    fmt: Format,
    fec_threshold: float = HD_FEC_THRESHOLD,
    baud: float = DEFAULT_BAUD,
    pols: int = DEFAULT_POLS,
) -> float:
    """OSNR (dB) at which the theoretical BER equals the FEC threshold."""
    return brentq(
        lambda osnr: ber_from_osnr(fmt, osnr, baud, pols) - fec_threshold,
        -10.0,
        40.0,
    )


def evaluate_link(
    fmt: Format,
    osnr_db: float,
    fec_threshold: float = HD_FEC_THRESHOLD,
    baud: float = DEFAULT_BAUD,
    pols: int = DEFAULT_POLS,
) -> LinkStatus:
    """BER, OSNR margin and alarms for a link running a given format."""
    ber = float(ber_from_osnr(fmt, osnr_db, baud, pols))
    margin = osnr_db - required_osnr_db(fmt, fec_threshold, baud, pols)
    alarms = (ALARM_BER_EXCEEDS_FEC,) if ber > fec_threshold else ()
    return LinkStatus(Format(fmt), osnr_db, ber, fec_threshold, margin, alarms)


def select_format(
    osnr_db: float,
    fec_threshold: float = HD_FEC_THRESHOLD,
    min_margin_db: float = 0.0,
    baud: float = DEFAULT_BAUD,
    pols: int = DEFAULT_POLS,
) -> LinkStatus:
    """Pick the highest-capacity format that clears the FEC threshold.

    If even QPSK fails, return the QPSK status (with its alarm) so the
    caller still sees why the link is down.
    """
    for fmt in FORMATS_BY_CAPACITY:
        status = evaluate_link(fmt, osnr_db, fec_threshold, baud, pols)
        if status.ok and status.margin_db >= min_margin_db:
            return status
    return status
