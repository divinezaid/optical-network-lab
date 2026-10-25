"""Link behaviour: FEC alarm and stepping down to a more robust format."""

import pytest

from linkmodel import (
    ALARM_BER_EXCEEDS_FEC,
    HD_FEC_THRESHOLD,
    Format,
    ber_from_osnr,
    evaluate_link,
    required_osnr_db,
    select_format,
)


@pytest.mark.parametrize("fmt", list(Format))
def test_required_osnr_hits_the_threshold(fmt):
    assert ber_from_osnr(fmt, required_osnr_db(fmt)) == pytest.approx(HD_FEC_THRESHOLD, rel=1e-6)


def test_required_osnr_ordering_and_ballpark():
    req = {f: required_osnr_db(f) for f in Format}
    assert req[Format.QPSK] < req[Format.QAM8] < req[Format.QAM16]
    # 32 GBaud DP-QPSK at HD-FEC needs ~12-13 dB, a well-known figure.
    assert 12.0 < req[Format.QPSK] < 13.5


@pytest.mark.parametrize("fmt", list(Format))
def test_no_alarm_with_margin(fmt):
    status = evaluate_link(fmt, required_osnr_db(fmt) + 1.0)
    assert status.ok
    assert status.margin_db == pytest.approx(1.0)


@pytest.mark.parametrize("fmt", list(Format))
def test_alarm_when_osnr_degrades_below_required(fmt):
    status = evaluate_link(fmt, required_osnr_db(fmt) - 0.5)
    assert ALARM_BER_EXCEEDS_FEC in status.alarms
    assert status.ber > HD_FEC_THRESHOLD
    assert status.margin_db < 0


def test_select_format_prefers_highest_capacity():
    assert select_format(30.0).format is Format.QAM16


def test_select_format_steps_down_as_osnr_drops():
    req = {f: required_osnr_db(f) for f in Format}
    between_8_and_16 = (req[Format.QAM8] + req[Format.QAM16]) / 2
    between_qpsk_and_8 = (req[Format.QPSK] + req[Format.QAM8]) / 2
    assert select_format(between_8_and_16).format is Format.QAM8
    assert select_format(between_qpsk_and_8).format is Format.QPSK


def test_select_format_reports_alarm_when_nothing_works():
    status = select_format(5.0)
    assert status.format is Format.QPSK
    assert not status.ok


def test_select_format_respects_margin():
    req16 = required_osnr_db(Format.QAM16)
    # 0.5 dB above 16-QAM's requirement, but we demand 1 dB margin.
    assert select_format(req16 + 0.5, min_margin_db=1.0).format is not Format.QAM16
