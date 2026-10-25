"""Thin client for one node's NBI and its /sim test-set endpoints.

Every call raises httpx.HTTPStatusError on a 4xx/5xx response, so a
negative test reads as:

    with pytest.raises(httpx.HTTPStatusError) as err:
        client.provision(...)
    assert err.value.response.status_code == 409
"""

from __future__ import annotations

import httpx


class NbiClient:
    def __init__(self, base_url: str, timeout_s: float = 5.0) -> None:
        self.base_url = base_url
        self.http = httpx.Client(base_url=base_url, timeout=timeout_s)

    def close(self) -> None:
        self.http.close()

    def _call(self, method: str, path: str, **kwargs):
        response = self.http.request(method, path, **kwargs)
        response.raise_for_status()
        return response.json() if response.content else None

    # ---- NBI -------------------------------------------------------------

    def health(self) -> dict:
        return self._call("GET", "/health")

    def ports(self) -> list[dict]:
        return self._call("GET", "/ports")

    def links(self) -> list[dict]:
        return self._call("GET", "/links")

    def link(self, link_id: str) -> dict:
        return self._call("GET", f"/links/{link_id}")

    def provision(self, link_id: str, *, port: str, peer: str, format: str = "AUTO", osnr_db: float = 22.0) -> dict:
        body = {"port": port, "peer": peer, "format": format, "osnr_db": osnr_db}
        return self._call("PUT", f"/links/{link_id}", json=body)

    def delete_link(self, link_id: str) -> None:
        self._call("DELETE", f"/links/{link_id}")

    def alarms(self, resource: str | None = None) -> list[dict]:
        params = {"resource": resource} if resource else None
        return self._call("GET", "/alarms", params=params)

    # ---- test set --------------------------------------------------------

    def cut_fiber(self, link_id: str) -> None:
        self._call("POST", f"/sim/links/{link_id}/fiber-cut")

    def repair_fiber(self, link_id: str) -> None:
        self._call("POST", f"/sim/links/{link_id}/repair")

    def set_osnr(self, link_id: str, osnr_db: float) -> None:
        self._call("PUT", f"/sim/links/{link_id}/osnr", json={"osnr_db": osnr_db})
