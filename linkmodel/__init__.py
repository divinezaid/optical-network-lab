"""Optical link model: modulation formats, BER vs OSNR, FEC alarms."""

from .ber import ber_from_osnr, ber_from_snr, qfunc
from .link import (
    ALARM_BER_EXCEEDS_FEC,
    FORMATS_BY_CAPACITY,
    HD_FEC_THRESHOLD,
    LinkStatus,
    evaluate_link,
    required_osnr_db,
    select_format,
)
from .modulation import Constellation, Format, constellation, demodulate, modulate
from .montecarlo import MonteCarloResult, simulate_ber, simulate_ber_osnr
from .osnr import osnr_to_snr_db, snr_to_osnr_db

__all__ = [
    "ALARM_BER_EXCEEDS_FEC",
    "FORMATS_BY_CAPACITY",
    "HD_FEC_THRESHOLD",
    "Constellation",
    "Format",
    "LinkStatus",
    "MonteCarloResult",
    "ber_from_osnr",
    "ber_from_snr",
    "constellation",
    "demodulate",
    "evaluate_link",
    "modulate",
    "osnr_to_snr_db",
    "qfunc",
    "required_osnr_db",
    "select_format",
    "simulate_ber",
    "simulate_ber_osnr",
    "snr_to_osnr_db",
]
