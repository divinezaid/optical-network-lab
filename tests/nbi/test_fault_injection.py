"""Fault injection: break the network, assert the right alarms appear in time.

Each test checks three things:
  1. The expected alarm appears on the right resource within the timeout.
  2. No unrelated alarm appears anywhere else (fault isolation).
  3. The alarm clears once the fault is removed.
"""

import time

import pytest

from linkmodel import Format, required_osnr_db
from verification.topology import RING, cut_fiber, provision_span, repair_fiber, set_span_osnr
from verification.waits import wait_for

from .conftest import ALARM_TIMEOUT_S

LOS = "LOS"
BER = "PRE_FEC_BER_EXCEEDS_THRESHOLD"
SPAN = RING[0]  # node-a <-> node-b


def alarm_types(client, link_id):
    return {a["type"] for a in client.alarms(resource=link_id)}


def wait_for_alarms(net, span, expected: set[str]):
    """Wait until both ends of `span` show exactly `expected`; return elapsed s."""
    start = time.monotonic()
    for node, _ in span.ends:
        wait_for(
            lambda: alarm_types(net[node], span.link_id) == expected,
            timeout_s=ALARM_TIMEOUT_S,
            what=f"{sorted(expected)} on {node}/{span.link_id}",
        )
    return time.monotonic() - start


def assert_no_alarms_outside(net, span):
    for client in net.values():
        stray = [a for a in client.alarms() if a["resource"] != span.link_id]
        assert stray == [], f"unexpected alarms on {client.base_url}: {stray}"


@pytest.fixture
def ring_up(net):
    for span in RING:
        provision_span(net, span, osnr_db=22.0)
    for span in RING:
        wait_for_alarms(net, span, set())
        for node, _ in span.ends:
            wait_for(lambda: net[node].link(span.link_id)["oper_state"] == "UP", timeout_s=ALARM_TIMEOUT_S)
    return net


def test_fiber_cut_raises_los_on_both_ends(ring_up):
    net = ring_up
    cut_fiber(net, SPAN)
    elapsed = wait_for_alarms(net, SPAN, {LOS})

    for node, _ in SPAN.ends:
        link = net[node].link(SPAN.link_id)
        assert link["oper_state"] == "DOWN"
        [alarm] = net[node].alarms(resource=SPAN.link_id)
        assert alarm["severity"] == "CRITICAL"
    assert_no_alarms_outside(net, SPAN)
    assert elapsed < ALARM_TIMEOUT_S


def test_fiber_repair_clears_los(ring_up):
    net = ring_up
    cut_fiber(net, SPAN)
    wait_for_alarms(net, SPAN, {LOS})
    repair_fiber(net, SPAN)
    wait_for_alarms(net, SPAN, set())
    for node, _ in SPAN.ends:
        assert net[node].link(SPAN.link_id)["oper_state"] == "UP"


def test_osnr_degradation_on_fixed_format_raises_ber_alarm(net):
    provision_span(net, SPAN, format="16-QAM", osnr_db=22.0)
    wait_for_alarms(net, SPAN, set())

    set_span_osnr(net, SPAN, required_osnr_db(Format.QAM16) - 1.0)
    wait_for_alarms(net, SPAN, {BER})
    for node, _ in SPAN.ends:
        link = net[node].link(SPAN.link_id)
        assert link["oper_state"] == "DEGRADED"
        assert link["active_format"] == "16-QAM"  # fixed format: no fallback
        assert link["margin_db"] < 0
        [alarm] = net[node].alarms(resource=SPAN.link_id)
        assert alarm["severity"] == "MAJOR"

    set_span_osnr(net, SPAN, 22.0)
    wait_for_alarms(net, SPAN, set())


@pytest.mark.parametrize(
    "osnr_db, expected_format, expected_alarms",
    [
        (22.0, "16-QAM", set()),
        (18.0, "8-QAM", set()),
        (14.0, "QPSK", set()),
        (10.0, "QPSK", {BER}),  # below even QPSK's requirement
    ],
)
def test_auto_format_steps_down_as_osnr_degrades(net, osnr_db, expected_format, expected_alarms):
    provision_span(net, SPAN, format="AUTO", osnr_db=22.0)
    wait_for_alarms(net, SPAN, set())

    set_span_osnr(net, SPAN, osnr_db)
    wait_for_alarms(net, SPAN, expected_alarms)
    for node, _ in SPAN.ends:
        wait_for(
            lambda: net[node].link(SPAN.link_id)["active_format"] == expected_format,
            timeout_s=ALARM_TIMEOUT_S,
            what=f"{expected_format} on {node}",
        )


def test_fiber_cut_masks_ber_alarm(net):
    """With no light, only LOS should show; the BER alarm is a symptom of it."""
    provision_span(net, SPAN, format="16-QAM", osnr_db=15.0)
    wait_for_alarms(net, SPAN, {BER})
    cut_fiber(net, SPAN)
    wait_for_alarms(net, SPAN, {LOS})
    repair_fiber(net, SPAN)
    wait_for_alarms(net, SPAN, {BER})  # underlying OSNR problem is still there


def test_alarm_id_is_stable_while_fault_persists(ring_up):
    """Re-evaluation must not re-raise (and re-number) a standing alarm."""
    net = ring_up
    cut_fiber(net, SPAN)
    wait_for_alarms(net, SPAN, {LOS})
    first = net["node-a"].alarms(resource=SPAN.link_id)
    time.sleep(1.0)  # several evaluation ticks
    assert net["node-a"].alarms(resource=SPAN.link_id) == first


def test_two_simultaneous_cuts_are_isolated(ring_up):
    net = ring_up
    far_span = RING[2]  # node-c <-> node-d, shares no node with SPAN
    cut_fiber(net, SPAN)
    cut_fiber(net, far_span)
    wait_for_alarms(net, SPAN, {LOS})
    wait_for_alarms(net, far_span, {LOS})
    for span in (RING[1], RING[3]):
        wait_for_alarms(net, span, set())
