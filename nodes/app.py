"""FastAPI app for one simulated network element.

Two groups of routes:
  - NBI (/health, /ports, /links, /alarms): what a management system or a
    test automation framework uses to configure and monitor the node.
  - /sim: the "test set". It injects faults (fiber cut, OSNR change) the
    way lab equipment would. Real gear has no such API; it exists here so
    tests can create faults on demand.

A background task re-evaluates links every `eval_interval_s`. Faults
therefore show up after a short delay, not instantly, which is why the
tests wait with a timeout instead of checking immediately.
"""

from __future__ import annotations

import asyncio
import logging
import traceback
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response, status
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .events import EventLog
from .models import Alarm, LinkConfig, LinkView, OsnrUpdate, Port
from .state import Conflict, NodeState, NotFound


def create_app(
    node_id: str,
    port_ids: list[str],
    *,
    eval_interval_s: float = 0.5,
    log_dir: Path | None = None,
) -> FastAPI:
    events = EventLog(node_id, log_dir)
    node = NodeState(node_id, port_ids, events)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        async def evaluation_loop() -> None:
            while True:
                try:
                    node.evaluate()
                except Exception:  # keep the node alive, but make the failure loud
                    events.emit(logging.ERROR, "EVALUATION_FAILED", error=traceback.format_exc())
                await asyncio.sleep(eval_interval_s)

        task = asyncio.create_task(evaluation_loop())
        events.emit(logging.INFO, "NODE_STARTED", ports=port_ids, eval_interval_s=eval_interval_s)
        yield
        task.cancel()
        events.emit(logging.INFO, "NODE_STOPPED")

    app = FastAPI(title=f"{node_id} NBI", lifespan=lifespan)
    app.state.node = node

    # ---- error mapping ---------------------------------------------------

    @app.exception_handler(NotFound)
    async def not_found(request: Request, exc: NotFound):
        events.emit(logging.WARNING, "REQUEST_REJECTED", method=request.method, path=request.url.path, status=404, reason=str(exc))
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(Conflict)
    async def conflict(request: Request, exc: Conflict):
        events.emit(logging.WARNING, "REQUEST_REJECTED", method=request.method, path=request.url.path, status=409, reason=str(exc))
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(RequestValidationError)
    async def invalid(request: Request, exc: RequestValidationError):
        events.emit(logging.WARNING, "REQUEST_REJECTED", method=request.method, path=request.url.path, status=422, reason=str(exc.errors()))
        return await request_validation_exception_handler(request, exc)

    # ---- NBI -------------------------------------------------------------

    @app.get("/health")
    async def health() -> dict:
        return {"node": node_id, "status": "ok"}

    @app.get("/ports")
    async def list_ports() -> list[Port]:
        return node.port_views()

    @app.get("/links")
    async def list_links() -> list[LinkView]:
        return [link.view() for link in node.links.values()]

    @app.get("/links/{link_id}")
    async def get_link(link_id: str) -> LinkView:
        return node.link(link_id).view()

    @app.put("/links/{link_id}")
    async def put_link(link_id: str, config: LinkConfig, response: Response) -> LinkView:
        created = node.provision(link_id, config)
        response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return node.links[link_id].view()

    @app.delete("/links/{link_id}", status_code=204)
    async def delete_link(link_id: str) -> None:
        node.delete(link_id)

    @app.get("/alarms")
    async def list_alarms(resource: str | None = None) -> list[Alarm]:
        return node.alarm_list(resource)

    # ---- simulation control (test set) -----------------------------------

    @app.post("/sim/links/{link_id}/fiber-cut", status_code=204)
    async def fiber_cut(link_id: str) -> None:
        node.cut_fiber(link_id)

    @app.post("/sim/links/{link_id}/repair", status_code=204)
    async def repair(link_id: str) -> None:
        node.repair_fiber(link_id)

    @app.put("/sim/links/{link_id}/osnr", status_code=204)
    async def set_osnr(link_id: str, update: OsnrUpdate) -> None:
        node.set_osnr(link_id, update.osnr_db)

    return app
