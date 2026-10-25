"""The test network: four nodes in a ring, and span-level operations.

A span is one fiber connecting two nodes. Each node only manages its own
end, so provisioning a span means configuring both ends. A fiber cut, like
a real backhoe, hits both ends at once.
"""

from __future__ import annotations

from dataclasses import dataclass

from .nbi_client import NbiClient

NODES = ("node-a", "node-b", "node-c", "node-d")


@dataclass(frozen=True)
class Span:
    link_id: str
    a: str
    a_port: str
    b: str
    b_port: str

    @property
    def ends(self) -> tuple[tuple[str, str], tuple[str, str]]:
        return (self.a, self.a_port), (self.b, self.b_port)


# node-a L1 <-> L2 node-b L1 <-> L2 node-c ... node-d L1 <-> L2 node-a
RING = tuple(
    Span(f"{a[-1]}-{b[-1]}", a, "L1", b, "L2")
    for a, b in zip(NODES, NODES[1:] + NODES[:1])
)

Network = dict[str, NbiClient]


def provision_span(net: Network, span: Span, *, format: str = "AUTO", osnr_db: float = 22.0) -> None:
    net[span.a].provision(span.link_id, port=span.a_port, peer=span.b, format=format, osnr_db=osnr_db)
    net[span.b].provision(span.link_id, port=span.b_port, peer=span.a, format=format, osnr_db=osnr_db)


def cut_fiber(net: Network, span: Span) -> None:
    for node, _ in span.ends:
        net[node].cut_fiber(span.link_id)


def repair_fiber(net: Network, span: Span) -> None:
    for node, _ in span.ends:
        net[node].repair_fiber(span.link_id)


def set_span_osnr(net: Network, span: Span, osnr_db: float) -> None:
    for node, _ in span.ends:
        net[node].set_osnr(span.link_id, osnr_db)
