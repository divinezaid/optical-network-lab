"""Fixtures for end-to-end NBI tests against a live four-node network.

By default the nodes start as local processes (no Docker needed). To test
the docker-compose network instead, point NBI_URLS at it:

    NBI_URLS=node-a=http://localhost:8001,node-b=http://localhost:8002,...
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from verification.nbi_client import NbiClient
from verification.topology import NODES, Network
from verification.waits import wait_for

ROOT = Path(__file__).resolve().parents[2]
BASE_PORT = 18001
LOCAL_EVAL_INTERVAL_S = "0.2"

# How long a node may take to react to a fault. Generous compared with the
# evaluation interval, so slow CI machines don't produce false failures.
ALARM_TIMEOUT_S = 3.0


def _start_local_nodes() -> tuple[dict[str, str], list[subprocess.Popen]]:
    env = {**os.environ, "LOG_DIR": str(ROOT / "logs"), "EVAL_INTERVAL_S": LOCAL_EVAL_INTERVAL_S}
    procs, urls = [], {}
    for i, name in enumerate(NODES):
        port = BASE_PORT + i
        procs.append(
            subprocess.Popen(
                [sys.executable, "-m", "nodes", "--id", name, "--host", "127.0.0.1", "--http-port", str(port)],
                cwd=ROOT,
                env=env,
                stdout=subprocess.DEVNULL,  # the JSON log file is the record
            )
        )
        urls[name] = f"http://127.0.0.1:{port}"
    return urls, procs


@pytest.fixture(scope="session")
def net() -> Network:
    procs: list[subprocess.Popen] = []
    if os.environ.get("NBI_URLS"):
        urls = dict(item.split("=", 1) for item in os.environ["NBI_URLS"].split(","))
    else:
        urls, procs = _start_local_nodes()

    clients = {name: NbiClient(url) for name, url in urls.items()}
    try:
        wait_for(
            lambda: all(c.health()["status"] == "ok" for c in clients.values()),
            timeout_s=20,
            what="all nodes healthy",
        )
        yield clients
    finally:
        for client in clients.values():
            client.close()
        for proc in procs:
            proc.terminate()
            proc.wait(timeout=10)


@pytest.fixture(autouse=True)
def clean_network(net: Network):
    """Every test starts from an empty network: no links, so no alarms."""
    def wipe():
        for client in net.values():
            for link in client.links():
                client.delete_link(link["link_id"])

    wipe()
    yield
    wipe()
