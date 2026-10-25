"""Run one node:  python -m nodes --id node-a --http-port 8001

Every option can also come from an environment variable (NODE_ID, PORTS,
HTTP_PORT, LOG_DIR, EVAL_INTERVAL_S), which is how docker-compose
configures each container.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import uvicorn

from .app import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulated optical network element")
    parser.add_argument("--id", default=os.environ.get("NODE_ID", "node-a"))
    parser.add_argument("--ports", default=os.environ.get("PORTS", "L1,L2"), help="comma-separated line ports")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--http-port", type=int, default=int(os.environ.get("HTTP_PORT", "8000")))
    parser.add_argument("--log-dir", default=os.environ.get("LOG_DIR", "logs"))
    parser.add_argument("--eval-interval", type=float, default=float(os.environ.get("EVAL_INTERVAL_S", "0.5")))
    args = parser.parse_args()

    app = create_app(
        args.id,
        args.ports.split(","),
        eval_interval_s=args.eval_interval,
        log_dir=Path(args.log_dir),
    )
    uvicorn.run(app, host=args.host, port=args.http_port, log_level="warning")


if __name__ == "__main__":
    main()
