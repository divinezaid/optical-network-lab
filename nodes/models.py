"""Request and response schemas for the node's northbound interface (NBI)."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class FormatSetting(str, Enum):
    QPSK = "QPSK"
    QAM8 = "8-QAM"
    QAM16 = "16-QAM"
    AUTO = "AUTO"  # node picks the highest-capacity format that clears FEC


class OperState(str, Enum):
    INIT = "INIT"  # provisioned, not yet evaluated (laser turn-up)
    UP = "UP"
    DEGRADED = "DEGRADED"  # carrying traffic but pre-FEC BER over threshold
    DOWN = "DOWN"  # no light


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    MAJOR = "MAJOR"
    MINOR = "MINOR"


class LinkConfig(BaseModel):
    port: str
    peer: str
    format: FormatSetting = FormatSetting.AUTO
    osnr_db: float = Field(ge=0, le=40, description="Received OSNR at this end, dB")


class LinkView(BaseModel):
    link_id: str
    port: str
    peer: str
    format: FormatSetting
    active_format: str | None
    osnr_db: float
    ber: float | None
    margin_db: float | None
    oper_state: OperState
    fiber_ok: bool


class Port(BaseModel):
    id: str
    link_id: str | None


class Alarm(BaseModel):
    id: int
    type: str
    severity: Severity
    resource: str
    description: str
    raised_at: datetime


class OsnrUpdate(BaseModel):
    osnr_db: float = Field(ge=0, le=40)
