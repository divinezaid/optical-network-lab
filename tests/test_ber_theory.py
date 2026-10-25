"""Theoretical BER: known reference values and physical sanity checks."""

import numpy as np
import pytest

from linkmodel import Format, ber_from_osnr, ber_from_snr, osnr_to_snr_db, snr_to_osnr_db


def test_qpsk_matches_textbook_value():
    # QPSK: BER = Q(sqrt(Es/N0)) = Q(sqrt(2 Eb/N0)). At Eb/N0 = 9.6 dB the
    # textbook BER is ~1e-5; Es/N0 is 3.01 dB higher for 2 bits/symbol.
    assert ber_from_snr(Format.QPSK, 9.6 + 10 * np.log10(2)) == pytest.approx(1e-5, rel=0.05)


def test_16qam_matches_high_snr_approximation():
    # At high SNR the exact formula converges to (3/8) erfc(sqrt(SNR/10)).
    from scipy.special import erfc

    snr_db = 20.0
    snr = 10 ** (snr_db / 10)
    approx = 3 / 8 * erfc(np.sqrt(snr / 10))
    assert ber_from_snr(Format.QAM16, snr_db) == pytest.approx(approx, rel=1e-3)


@pytest.mark.parametrize("fmt", list(Format))
def test_ber_decreases_with_osnr(fmt):
    osnr = np.linspace(5, 25, 41)
    assert np.all(np.diff(ber_from_osnr(fmt, osnr)) < 0)


@pytest.mark.parametrize("fmt", list(Format))
def test_ber_is_half_with_no_signal(fmt):
    # At vanishing SNR every bit is a coin flip.
    assert ber_from_snr(fmt, -60.0) == pytest.approx(0.5, abs=1e-3)


def test_higher_order_formats_need_more_osnr():
    osnr = np.linspace(8, 25, 35)
    qpsk, qam8, qam16 = (ber_from_osnr(f, osnr) for f in Format)
    assert np.all(qpsk < qam8) and np.all(qam8 < qam16)


def test_osnr_snr_conversion():
    # 32 GBaud, dual-pol, 12.5 GHz reference: SNR = OSNR - 10log10(32/12.5)
    assert osnr_to_snr_db(20.0) == pytest.approx(20.0 - 10 * np.log10(32 / 12.5))
    assert snr_to_osnr_db(osnr_to_snr_db(17.3)) == pytest.approx(17.3)
