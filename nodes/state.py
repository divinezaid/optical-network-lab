"""A network element's state: ports, links and alarms.

Pure Python with no web framework, so the behaviour can be unit-tested
directly. The HTTP layer (app.py) only translates requests into calls here.

Alarm rules, evaluated on every tick:
  - Fiber cut              -> LOS (critical), link DOWN.
  - Pre-FEC BER > FEC limit -> PRE_FEC_BER_EXCEEDS_THRESHOLD (major), link DEGRADED.
  - LOS masks the BER alarm: with no light there is no BER to report, and
    raising both would send operators chasing a secondary symptom.
  - Alarms are keyed by (type, resource), so repeated ticks don't duplicate
    them, and they clear automatically when the condition goes away.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from linkmodel import ALARM_BER_EXCEEDS_FEC, HD_FEC_THRESHOLD, Format, evaluate_link, select_format

from .events import EventLog
from .models import Alarm, FormatSetting, LinkConfig, LinkView, OperState, Port, Severity

ALARM_LOS = "LOS"


class NotFound(Exception):
    pass


class Conflict(Exception):
    pass


@dataclass
class Link:
    link_id: str
    config: LinkConfig
    osnr_db: float
    fiber_ok: bool = True
    oper_state: OperState = OperState.INIT
    active_format: Format | None = None
    ber: float | None = None
    margin_db: float | None = None

    def view(self) -> LinkView:
        return LinkView(
            link_id=self.link_id,
            port=self.config.port,
            peer=self.config.peer,
            format=self.config.format,
            active_format=self.active_format.value if self.active_format else None,
            osnr_db=self.osnr_db,
            ber=self.ber,
            margin_db=self.margin_db,
            oper_state=self.oper_state,
            fiber_ok=self.fiber_ok,
        )


class NodeState:
    def __init__(
        self,
        node_id: str,
        port_ids: list[str],
        events: EventLog,
        fec_threshold: float = HD_FEC_THRESHOLD,
    ) -> None:
        self.node_id = node_id
        self.events = events
        self.fec_threshold = fec_threshold
        self.ports: dict[str, str | None] = {p: None for p in port_ids}  # port -> link_id
        self.links: dict[str, Link] = {}
        self.alarms: dict[tuple[str, str], Alarm] = {}
        self._next_alarm_id = 1

    # ---- configuration (NBI) ---------------------------------------------

    def provision(self, link_id: str, config: LinkConfig) -> bool:
        """Create or replace a link. Returns True if it was newly created."""
        if config.port not in self.ports:
            raise NotFound(f"port {config.port} does not exist")
        owner = self.ports[config.port]
        if owner is not None and owner != link_id:
            raise Conflict(f"port {config.port} is in use by link {owner}")

        existing = self.links.get(link_id)
        if existing and existing.config.port != config.port:
            self.ports[existing.config.port] = None

        self.ports[config.port] = link_id
        self.links[link_id] = Link(link_id, config, osnr_db=config.osnr_db)
        self.events.emit(
            logging.INFO,
            "LINK_REPROVISIONED" if existing else "LINK_PROVISIONED",
            link_id=link_id,
            **config.model_dump(mode="json"),
        )
        return existing is None

    def delete(self, link_id: str) -> None:
        link = self.link(link_id)
        self.ports[link.config.port] = None
        del self.links[link_id]
        for alarm_type, resource in list(self.alarms):
            if resource == link_id:
                self._clear(alarm_type, resource)
        self.events.emit(logging.INFO, "LINK_DELETED", link_id=link_id)

    def port_views(self) -> list[Port]:
        return [Port(id=p, link_id=l) for p, l in self.ports.items()]

    def alarm_list(self, resource: str | None = None) -> list[Alarm]:
        return [a for a in self.alarms.values() if resource is None or a.resource == resource]

    # ---- fault injection (simulation control, not part of the NBI) -------

    def cut_fiber(self, link_id: str) -> None:
        self.link(link_id).fiber_ok = False
        self.events.emit(logging.INFO, "FIBER_CUT_INJECTED", link_id=link_id)

    def repair_fiber(self, link_id: str) -> None:
        self.link(link_id).fiber_ok = True
        self.events.emit(logging.INFO, "FIBER_REPAIRED", link_id=link_id)

    def set_osnr(self, link_id: str, osnr_db: float) -> None:
        link = self.link(link_id)
        self.events.emit(logging.INFO, "OSNR_CHANGED", link_id=link_id, old=link.osnr_db, new=osnr_db)
        link.osnr_db = osnr_db

    # ---- periodic evaluation ---------------------------------------------

    def evaluate(self) -> None:
        for link in self.links.values():
            self._evaluate_link(link)

    def _evaluate_link(self, link: Link) -> None:
        if not link.fiber_ok:
            link.ber = link.margin_db = None
            self._clear(ALARM_BER_EXCEEDS_FEC, link.link_id)  # masked by LOS
            self._raise(ALARM_LOS, Severity.CRITICAL, link.link_id, "Loss of signal")
            self._set_oper_state(link, OperState.DOWN)
            return
        self._clear(ALARM_LOS, link.link_id)

        if link.config.format is FormatSetting.AUTO:
            status = select_format(link.osnr_db, self.fec_threshold)
        else:
            status = evaluate_link(Format(link.config.format.value), link.osnr_db, self.fec_threshold)

        if link.active_format is not None and status.format != link.active_format:
            self.events.emit(
                logging.WARNING,
                "MODULATION_CHANGED",
                link_id=link.link_id,
                old=link.active_format.value,
                new=status.format.value,
                osnr_db=link.osnr_db,
            )
        link.active_format = status.format
        link.ber = status.ber
        link.margin_db = round(status.margin_db, 2)

        if status.ok:
            self._clear(ALARM_BER_EXCEEDS_FEC, link.link_id)
            self._set_oper_state(link, OperState.UP)
        else:
            self._raise(
                ALARM_BER_EXCEEDS_FEC,
                Severity.MAJOR,
                link.link_id,
                f"Pre-FEC BER {status.ber:.2e} above {self.fec_threshold:.1e}",
            )
            self._set_oper_state(link, OperState.DEGRADED)

    # ---- helpers ---------------------------------------------------------

    def link(self, link_id: str) -> Link:
        try:
            return self.links[link_id]
        except KeyError:
            raise NotFound(f"link {link_id} does not exist") from None

    def _set_oper_state(self, link: Link, state: OperState) -> None:
        if link.oper_state is not state:
            self.events.emit(
                logging.INFO, "LINK_STATE_CHANGED", link_id=link.link_id, old=link.oper_state.value, new=state.value
            )
            link.oper_state = state

    def _raise(self, alarm_type: str, severity: Severity, resource: str, description: str) -> None:
        key = (alarm_type, resource)
        if key in self.alarms:
            return
        alarm = Alarm(
            id=self._next_alarm_id,
            type=alarm_type,
            severity=severity,
            resource=resource,
            description=description,
            raised_at=datetime.now(timezone.utc),
        )
        self._next_alarm_id += 1
        self.alarms[key] = alarm
        level = logging.ERROR if severity is Severity.CRITICAL else logging.WARNING
        self.events.emit(level, "ALARM_RAISED", **alarm.model_dump(mode="json"))

    def _clear(self, alarm_type: str, resource: str) -> None:
        alarm = self.alarms.pop((alarm_type, resource), None)
        if alarm is not None:
            self.events.emit(logging.INFO, "ALARM_CLEARED", id=alarm.id, type=alarm_type, resource=resource)
