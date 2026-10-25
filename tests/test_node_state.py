"""Unit tests for the node state machine, no HTTP involved."""

import pytest

from linkmodel import ALARM_BER_EXCEEDS_FEC, Format, required_osnr_db
from nodes.events import EventLog
from nodes.models import FormatSetting, LinkConfig, OperState
from nodes.state import ALARM_LOS, Conflict, NodeState, NotFound


@pytest.fixture
def node():
    return NodeState("unit", ["L1", "L2"], EventLog("unit"))


def cfg(port="L1", fmt=FormatSetting.AUTO, osnr=22.0):
    return LinkConfig(port=port, peer="peer", format=fmt, osnr_db=osnr)


def alarm_types(node, link_id="x"):
    return {a.type for a in node.alarm_list(link_id)}


def test_provision_then_evaluate_brings_link_up(node):
    assert node.provision("x", cfg()) is True
    assert node.links["x"].oper_state is OperState.INIT
    node.evaluate()
    assert node.links["x"].oper_state is OperState.UP
    assert node.ports["L1"] == "x"


def test_reprovision_returns_false_and_moves_port(node):
    node.provision("x", cfg(port="L1"))
    assert node.provision("x", cfg(port="L2")) is False
    assert node.ports == {"L1": None, "L2": "x"}


def test_port_conflicts_and_unknowns(node):
    node.provision("x", cfg(port="L1"))
    with pytest.raises(Conflict):
        node.provision("y", cfg(port="L1"))
    with pytest.raises(NotFound):
        node.provision("y", cfg(port="L9"))
    with pytest.raises(NotFound):
        node.delete("nope")


def test_fiber_cut_raises_los_once_and_clears_on_repair(node):
    node.provision("x", cfg())
    node.cut_fiber("x")
    node.evaluate()
    node.evaluate()  # a second tick must not duplicate the alarm
    assert [a.type for a in node.alarm_list("x")] == [ALARM_LOS]
    assert node.links["x"].oper_state is OperState.DOWN

    node.repair_fiber("x")
    node.evaluate()
    assert node.alarm_list("x") == []
    assert node.links["x"].oper_state is OperState.UP


def test_ber_alarm_on_fixed_format(node):
    node.provision("x", cfg(fmt=FormatSetting.QAM16, osnr=required_osnr_db(Format.QAM16) - 1))
    node.evaluate()
    assert alarm_types(node) == {ALARM_BER_EXCEEDS_FEC}
    assert node.links["x"].oper_state is OperState.DEGRADED


def test_los_masks_ber_alarm(node):
    node.provision("x", cfg(fmt=FormatSetting.QAM16, osnr=15.0))
    node.evaluate()
    assert alarm_types(node) == {ALARM_BER_EXCEEDS_FEC}
    node.cut_fiber("x")
    node.evaluate()
    assert alarm_types(node) == {ALARM_LOS}


def test_auto_format_steps_down_instead_of_alarming(node):
    node.provision("x", cfg(osnr=22.0))
    node.evaluate()
    assert node.links["x"].active_format is Format.QAM16
    node.set_osnr("x", 18.0)
    node.evaluate()
    assert node.links["x"].active_format is Format.QAM8
    assert node.alarm_list("x") == []


def test_delete_clears_link_alarms(node):
    node.provision("x", cfg())
    node.cut_fiber("x")
    node.evaluate()
    node.delete("x")
    assert node.alarm_list() == []
    assert node.ports["L1"] is None
