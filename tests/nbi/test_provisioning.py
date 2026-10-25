"""Functional tests: provision links and check their state through the NBI."""

import httpx
import pytest

from verification.topology import NODES, RING, provision_span
from verification.waits import wait_for

from .conftest import ALARM_TIMEOUT_S


def wait_for_state(client, link_id, state):
    return wait_for(
        lambda: (link := client.link(link_id))["oper_state"] == state and link,
        timeout_s=ALARM_TIMEOUT_S,
        what=f"{link_id} {state} on {client.base_url}",
    )


def test_all_nodes_healthy(net):
    assert {c.health()["node"] for c in net.values()} == set(NODES)


def test_nodes_start_with_free_ports_and_no_alarms(net):
    for client in net.values():
        assert client.ports() == [{"id": "L1", "link_id": None}, {"id": "L2", "link_id": None}]
        assert client.alarms() == []


def test_provision_link_comes_up(net):
    a = net["node-a"]
    link = a.provision("t1", port="L1", peer="node-b", format="QPSK", osnr_db=20.0)
    assert link["oper_state"] == "INIT"
    assert link["format"] == "QPSK"

    link = wait_for_state(a, "t1", "UP")
    assert link["active_format"] == "QPSK"
    assert link["margin_db"] > 0
    assert {"id": "L1", "link_id": "t1"} in a.ports()


def test_auto_format_picks_highest_capacity(net):
    a = net["node-a"]
    a.provision("t1", port="L1", peer="node-b", format="AUTO", osnr_db=22.0)
    assert wait_for_state(a, "t1", "UP")["active_format"] == "16-QAM"


def test_put_is_idempotent_and_reprovisions(net):
    a = net["node-a"]
    a.provision("t1", port="L1", peer="node-b", format="QPSK")
    response = a.http.put("/links/t1", json={"port": "L1", "peer": "node-b", "format": "8-QAM", "osnr_db": 22.0})
    assert response.status_code == 200
    assert wait_for_state(a, "t1", "UP")["active_format"] == "8-QAM"
    assert len(a.links()) == 1


def test_delete_frees_port(net):
    a = net["node-a"]
    a.provision("t1", port="L1", peer="node-b")
    a.delete_link("t1")
    assert a.links() == []
    assert {"id": "L1", "link_id": None} in a.ports()
    with pytest.raises(httpx.HTTPStatusError) as err:
        a.link("t1")
    assert err.value.response.status_code == 404


@pytest.mark.parametrize(
    "body, status",
    [
        ({"port": "L9", "peer": "node-b", "format": "QPSK", "osnr_db": 20}, 404),  # no such port
        ({"port": "L1", "peer": "node-b", "format": "64-QAM", "osnr_db": 20}, 422),  # unsupported format
        ({"port": "L1", "peer": "node-b", "format": "QPSK", "osnr_db": 99}, 422),  # OSNR out of range
        ({"port": "L1", "format": "QPSK", "osnr_db": 20}, 422),  # missing peer
    ],
    ids=["unknown-port", "bad-format", "osnr-out-of-range", "missing-peer"],
)
def test_invalid_provisioning_is_rejected(net, body, status):
    response = net["node-a"].http.put("/links/bad", json=body)
    assert response.status_code == status
    assert net["node-a"].links() == []  # nothing half-created


def test_port_already_in_use_is_rejected(net):
    a = net["node-a"]
    a.provision("t1", port="L1", peer="node-b")
    with pytest.raises(httpx.HTTPStatusError) as err:
        a.provision("t2", port="L1", peer="node-c")
    assert err.value.response.status_code == 409
    assert [l["link_id"] for l in a.links()] == ["t1"]


def test_full_ring_comes_up_clean(net):
    for span in RING:
        provision_span(net, span)
    for span in RING:
        for node, port in span.ends:
            link = wait_for_state(net[node], span.link_id, "UP")
            assert link["port"] == port
    assert all(c.alarms() == [] for c in net.values())
